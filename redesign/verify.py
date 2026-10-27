#!/usr/bin/env python3
"""Draft checks: native ERC, exported pin parity, and passive recovery topology.

The graph models power terminals, body diodes and selectable fuse connections;
it is not a simulation of semiconductor damage, signal paths, or fuse clearing.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'tools'))
from sexp import parse_one, find, find_all
import circuit
import protection_topology


def circuit_checks():
    parts = circuit.build()
    refs = {p.ref: p for p in parts}
    assert len(refs) == len(parts), 'Duplicate reference'
    req = json.loads((HERE / 'requirements.json').read_text())
    assert [c[0] for c in circuit.CHANNELS] == req['channel_fuse_maxima_a']
    pins = [p for group in (circuit.ADC, circuit.CONTROL, circuit.DIAG) for p, _ in group]
    gpios = [g for group in (circuit.ADC, circuit.CONTROL, circuit.DIAG) for _, g in group]
    assert len(set(pins)) == len(pins) == 24
    assert len(set(gpios)) == 24 and not set(gpios) & {0, 19, 20, 43, 44, 45, 46}
    assert [g for _, g in circuit.ADC] == list(range(1, 9))
    assert refs['F9'].pins == {'1': 'AUTO_PROTECTED', '2': 'LOGIC_FUSED'}
    assert refs['F10'].pins == {'1': 'BATT_RAW', '2': 'AUTO_FUSED'}
    for n in range(6, 10):
        assert refs[f'Q{n}'].pins == {'1': f'HGATE_Q{n}', '2': 'PROTECTION_COMMON_SOURCE', '3': 'AUTO_FUSED'}
    for n in (10, 11):
        assert refs[f'Q{n}'].pins == {'1': 'PROTECTION_COMMON_SOURCE', '2': 'PROTECTION_COMMON_SOURCE',
                                     '3': 'PROTECTION_COMMON_SOURCE', '4': f'DGATE_Q{n}', '5': 'AUTO_PROTECTED'}
    assert refs['U15'].pins == {'1': 'DGATE_AUTO', '2': 'PROTECTION_COMMON_SOURCE',
                              '3': 'PROTECTION_COMMON_SOURCE', '4': 'PROTECTION_COMMON_SOURCE',
                              '5': 'OV_AUTO', '6': 'VS_CONTROLLER', '7': 'GND', '8': 'HGATE_AUTO',
                              '9': 'PROTECTION_COMMON_SOURCE', '10': 'VS_CONTROLLER',
                              '11': 'CAP_AUTO', '12': 'AUTO_PROTECTED'}
    for n in range(1, 9):
        assert refs[f'F{n}'].pins == protection_topology.selector_pins(n)
        assert refs[f'J{n+10}'].pins == {'1': f'LOAD{n}', '2': 'GND'}
        assert refs[f'U{n}'].pins['15'] == 'AUTO_PROTECTED'
        assert refs[f'U{n}'].pins['8'] == f'PROFET_OUT{n}'
        assert {p.ref for p in parts if f'LOAD{n}' in p.pins.values()} == {f'F{n}', f'J{n+10}'}, 'BYPASS load must have no electronic/shunt attachments'
        assert refs[f'R{n}08'].pins == {'1': f'INR{n}', '2': f'UGND{n}'}
        assert refs[f'R{n}09'].pins == {'1': f'DENR{n}', '2': f'UGND{n}'}
        assert refs[f'D{n}03'].pins == {'1': 'GND', '2': f'LEDK{n}', '3': 'GND'}
    expected = {f'F{n}' for n in range(1, 9)} | {'F10', 'J2', '#FLG1'}
    assert {p.ref for p in parts if 'BATT_RAW' in p.pins.values()} == expected
    return refs


def recovery_checks(refs):
    result = protection_topology.check(refs)
    print(f"Power-path graph: {result['mode_cases']} mode/supply combinations; "
          f"{result['fault_recovery_cases']} shared-fuse isolation cases passed")
    return result['mode_cases'], result['fault_recovery_cases']


def netlist_check(path):
    doc = parse_one(path.read_text())
    expected = {}
    parts = {p.ref: p for p in circuit.build() if not p.ref.startswith('#')}
    for p in parts.values():
        for pin, net in p.pins.items():
            expected.setdefault(net, set()).add((p.ref, pin))
    # Physical stacked PROFET output pins, checked independently of the generator.
    for n in range(1, 9):
        expected[f'PROFET_OUT{n}'].update((f'U{n}', pin) for pin in ('9', '10', '12', '13', '14'))
    actual = {}
    for net in find_all(find(doc, 'nets'), 'net'):
        name = find(net, 'name')[1].lstrip('/')
        actual[name] = {(find(node, 'ref')[1], str(find(node, 'pin')[1]))
                        for node in find_all(net, 'node')}
    for net, want in expected.items():
        assert actual.get(net) == want, (net, 'missing', want - actual.get(net, set()),
                                         'extra', actual.get(net, set()) - want)
    for net, nodes in actual.items():
        assert net in expected or (net.startswith('unconnected-') and len(nodes) == 1), (net, nodes)
    components = {find(c, 'ref')[1]: c for c in find_all(find(doc, 'components'), 'comp')}
    assert set(components) == set(parts)
    for ref, part in parts.items():
        assert find(components[ref], 'value')[1] == part.value
        assert find(components[ref], 'footprint')[1] == part.footprint
        fields = {find(f, 'name')[1]: f[2] for f in find_all(find(components[ref], 'fields'), 'field') if len(f) > 2}
        if part.fields.get('MPN'):
            assert fields.get('MPN') == part.fields['MPN']
    print(f'Native netlist: {len(parts)} components; {sum(map(len, expected.values()))} connected physical pins match')


def main():
    import protection_screen, sense_screen, analysis
    for name,result in [('protection-screen.json',protection_screen.screen()),
                        ('sense-screen.json',sense_screen.screen()),('electrical-screen.json',analysis.analyze())]:
        (HERE/name).write_text(json.dumps(result,indent=2)+'\n')
    refs = circuit_checks()
    count, faults = recovery_checks(refs)
    cli = os.environ.get('KICAD_CLI')
    if not cli and Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli').is_file():
        cli = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
    cli = cli or shutil.which('kicad-cli')
    if not cli:
        raise RuntimeError('Install native KiCad or set KICAD_CLI')
    out = ROOT / 'out/redesign'
    out.mkdir(parents=True, exist_ok=True)
    log = out / 'kicad-cli.log'
    log.write_text('')

    def run(args):
        result = subprocess.run([cli, *args], capture_output=True, text=True)
        with log.open('a') as f:
            f.write(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'KiCad failed ({result.returncode}); see {log} and ERC report')

    source = HERE / 'eswitch-simple.kicad_sch'
    run(['sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', str(out / 'netlist.net'), str(source)])
    netlist_check(out / 'netlist.net')
    run(['sch', 'erc', '--severity-all', '--exit-code-violations', '--format', 'json',
         '-o', str(out / 'erc.json'), str(source)])
    run(['sch', 'export', 'svg', '-o', str(out / 'svg'), str(source)])
    run(['sch', 'export', 'pdf', '-o', str(out / 'eswitch-simple.pdf'), str(source)])
    report = json.loads((out / 'erc.json').read_text())
    violations = [v for sheet in report['sheets'] for v in sheet['violations']]
    assert not violations
    inputs = [HERE / n for n in ('circuit.py', 'generate.py', 'verify.py', 'requirements.json',
                                'eswitch-simple.kicad_sch', 'eswitch-simple.kicad_pro',
                                'BUILD.md', 'JLCPCB-ORDER.txt', 'jlc-stackup-evidence.json',
                                'jlc_feature_screen.py', 'installation_screen.py',
                                'installation-screen.json', 'export.py')]
    inputs.extend([ROOT / 'tools/gen_sch.py', HERE / 'lib/eswitch.kicad_sym',
                   HERE / 'input_protection.py', HERE / 'protection_topology.py',
                    HERE / 'protection_screen.py', HERE / 'protection-screen.json',
                    HERE / 'sense_screen.py', HERE / 'sense-screen.json',
                    HERE / 'analysis.py', HERE / 'electrical-screen.json',
                    HERE / 'PROTECTION-REVIEW.md'])
    board=HERE/'eswitch-simple.kicad_pcb'
    layout=None
    if board.exists():
        run(['pcb','drc','--refill-zones','--save-board','--schematic-parity','--severity-all',
             '--format','json','-o',str(out/'eswitch-simple-drc.json'),str(board)])
        layout=json.loads((out/'eswitch-simple-drc.json').read_text())
        assert not layout['violations'],layout['violations']
        assert not layout['unconnected_items'],layout['unconnected_items']
        assert not layout.get('schematic_parity'),layout.get('schematic_parity')
        python=os.environ.get('KICAD_PYTHON','/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9')
        geometry=subprocess.run([python,str(HERE/'power_geometry.py'),str(board),'--check',
                                 '--output',str(HERE/'power-copper-review.json')],capture_output=True,text=True)
        (out/'power-geometry.log').write_text(geometry.stdout+geometry.stderr)
        if geometry.returncode:raise RuntimeError('Power geometry regression failed; see out/redesign/power-geometry.log')
        inputs.extend([HERE/'power_geometry.py',HERE/'power-copper-review.json'])
        transitions=subprocess.run([python,str(HERE/'power_transitions.py'),str(board),
                                    '--output',str(HERE/'power-transition-review.json')],capture_output=True,text=True)
        (out/'power-transitions.log').write_text(transitions.stdout+transitions.stderr)
        if transitions.returncode:raise RuntimeError('Physical power transitions failed; see out/redesign/power-transitions.log')
        inputs.extend([HERE/'power_transitions.py',HERE/'power-transition-review.json'])
        inputs.append(board)
    summary = dict(status='layout_and_schematic_checks_passed_not_electrical_qualification' if layout else 'schematic_checks_passed_not_electrical_qualification',
                    erc_violations=len(violations), mode_switch_combinations=count,
                    fault_removal_cases=faults, native_pin_parity='passed',
                    pcb_drc_violations=len(layout['violations']) if layout else None,
                    pcb_unconnected=len(layout['unconnected_items']) if layout else None,
                    pcb_schematic_parity=len(layout.get('schematic_parity',[])) if layout else None,
                    connected_power_geometry='passed_not_ampacity_qualification' if layout else None,
                    source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    (out / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('Schematic'+(' and PCB layout' if layout else '')+' checks passed. Electrical/thermal qualification remains open.')


if __name__ == '__main__':
    main()
