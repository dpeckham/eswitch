#!/usr/bin/env python3
"""Draft checks: native ERC, exported pin parity, and passive recovery topology.

The graph models power terminals, body diodes and selectable fuse connections;
it is not a simulation of semiconductor damage, signal paths, or fuse clearing.
"""
import itertools
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
    assert refs['F9'].pins == {'1': 'BATT_RAW', '2': 'LOGIC_FUSED'}
    for n in range(1, 9):
        assert refs[f'F{n}'].pins == {'1': f'VS{n}', '2': 'BATT_RAW', '3': f'LOAD{n}'}
        assert refs[f'J{n+10}'].pins == {'1': f'LOAD{n}', '2': 'GND'}
        assert refs[f'U{n}'].pins['15'] == f'VS{n}'
        assert refs[f'U{n}'].pins['8'] == f'LOAD{n}'
        assert refs[f'R{n}08'].pins == {'1': f'INR{n}', '2': f'UGND{n}'}
        assert refs[f'R{n}09'].pins == {'1': f'DENR{n}', '2': f'UGND{n}'}
        assert refs[f'D{n}03'].pins == {'1': 'GND', '2': f'LEDK{n}', '3': 'GND'}
    # A hidden shared VS connection would defeat fuse removal and feed neighbors.
    for p in parts:
        vs_nets = {v for v in p.pins.values() if v in {f'VS{n}' for n in range(1, 9)}}
        assert len(vs_nets) <= 1, ('Cross-channel VS connection', p.ref)
    expected = {f'F{n}' for n in range(1, 10)} | {'J2'} | {'#FLG1'}
    assert {p.ref for p in parts if 'BATT_RAW' in p.pins.values()} == expected
    return refs


def recovery_checks(refs):
    def graph(modes, switches_on, fault=None):
        edges = {}

        def link(a, b, both=False):
            edges.setdefault(a, set()).add(b)
            if both:
                edges.setdefault(b, set()).add(a)

        for n, mode in enumerate(modes, 1):
            fuse, switch = refs[f'F{n}'], refs[f'U{n}']
            vs, out = switch.pins['15'], switch.pins['8']
            if mode != 'OFF':
                link(fuse.pins['2'], fuse.pins['1' if mode == 'AUTO' else '3'], True)
            link(out, vs)  # intrinsic diode, OUT -> VS
            if switches_on:
                link(vs, out)
            if fault and fault[0] == n:
                if fault[1] == 'stuck_on':
                    link(vs, out, True)
                else:
                    link(vs if fault[1] == 'vs_ground' else out, 'FAULT_GND', True)
        return edges

    def reachable(edges, start='BATT_RAW'):
        seen, pending = {start}, [start]
        while pending:
            for node in edges.get(pending.pop(), set()) - seen:
                seen.add(node)
                pending.append(node)
        return seen

    count = 0
    for modes in itertools.product(('AUTO', 'BYPASS', 'OFF'), repeat=8):
        for on in (False, True):
            reached = reachable(graph(modes, on))
            for n, mode in enumerate(modes, 1):
                assert (f'LOAD{n}' in reached) == (mode == 'BYPASS' or mode == 'AUTO' and on)
                assert (f'VS{n}' in reached) == (mode != 'OFF')
            count += 1
    faults = 0
    for n in range(1, 9):
        for kind in ('stuck_on', 'vs_ground', 'out_ground'):
            modes = ['BYPASS'] * 8
            before = reachable(graph(modes, False, (n, kind)))
            assert ('FAULT_GND' in before) == (kind != 'stuck_on')
            modes[n-1] = 'OFF'
            after = reachable(graph(modes, False, (n, kind)))
            assert 'FAULT_GND' not in after
            assert f'VS{n}' not in after and f'LOAD{n}' not in after
            assert all(f'LOAD{i}' in after for i in range(1, 9) if i != n)
            faults += 1
    print(f'Power-path graph: {count} mode/switch combinations; {faults} fault/removal cases passed')
    return count, faults


def netlist_check(path):
    doc = parse_one(path.read_text())
    expected = {}
    parts = {p.ref: p for p in circuit.build() if not p.ref.startswith('#')}
    for p in parts.values():
        for pin, net in p.pins.items():
            expected.setdefault(net, set()).add((p.ref, pin))
    # Physical stacked PROFET output pins, checked independently of the generator.
    for n in range(1, 9):
        expected[f'LOAD{n}'].update((f'U{n}', pin) for pin in ('9', '10', '12', '13', '14'))
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
    inputs.extend([ROOT / 'tools/gen_sch.py', ROOT / 'lib/eswitch.kicad_sym'])
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
