#!/usr/bin/env python3
"""Accepted power topology; graph checks, not a physical circuit simulation.

Kept separate from the old routed circuit until the protection revision is routed.
The model explicitly includes PROFET body diodes and a failed shared protector.
"""
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def selector_pins(channel):
    return {'1': f'PROFET_OUT{channel}', '2': f'LOAD{channel}', '3': 'BATT_RAW'}


def graph(modes, switches_on=False, protection_on=True, supply_fuse=True,
          fault=None, selector=selector_pins):
    edges = {}

    def link(a, b, both=False):
        edges.setdefault(a, set()).add(b)
        if both:
            edges.setdefault(b, set()).add(a)

    if supply_fuse:
        link('BATT_RAW', 'AUTO_FUSED', True)
    # Common-source MOSFET body diodes point OUTWARD from their common source.
    # Neither permits RAW -> protected rail with the cutoff MOSFET off.
    link('PROTECTION_COMMON_SOURCE', 'AUTO_FUSED')
    link('PROTECTION_COMMON_SOURCE', 'AUTO_PROTECTED')
    if protection_on or fault == 'protection_short':
        link('AUTO_FUSED', 'PROTECTION_COMMON_SOURCE', True)
        link('PROTECTION_COMMON_SOURCE', 'AUTO_PROTECTED', True)
    if fault == 'protected_ground':
        link('AUTO_PROTECTED', 'FAULT_GND', True)
    elif fault == 'fused_input_ground':
        link('AUTO_FUSED', 'FAULT_GND', True)
    for n, mode in enumerate(modes, 1):
        pins = selector(n)
        out = f'PROFET_OUT{n}'
        link(out, 'AUTO_PROTECTED')
        if switches_on:
            link('AUTO_PROTECTED', out)
        if mode != 'OFF':
            link(pins['2'], pins['1' if mode == 'AUTO' else '3'], True)
        if isinstance(fault, tuple) and fault[0] == n:
            if fault[1] == 'stuck_on':
                link('AUTO_PROTECTED', out, True)
            else:
                link('AUTO_PROTECTED' if fault[1] == 'vs_ground' else out,
                     'FAULT_GND', True)
    return edges


def reachable(edges, start='BATT_RAW'):
    seen, pending = {start}, [start]
    while pending:
        for node in edges.get(pending.pop(), set()) - seen:
            seen.add(node)
            pending.append(node)
    return seen


def check(refs=None):
    req = json.loads((HERE / 'requirements.json').read_text())
    assert req['protection']['movable_fuse_connections'] == selector_pins('n')
    assert req['recovery']['bypass_has_no_series_electronic_switch']
    assert req['recovery']['bypass_disconnects_load_from_profet_output']
    assert not req['recovery']['additional_fixed_fuse_per_channel']
    selector = selector_pins if refs is None else lambda n: refs[f'F{n}'].pins
    if refs is not None:
        assert refs['F10'].pins == {'1': 'BATT_RAW', '2': 'AUTO_FUSED'}
        for n in range(1, 9):
            assert refs[f'U{n}'].pins['8'] == f'PROFET_OUT{n}'
            assert refs[f'U{n}'].pins['15'] == 'AUTO_PROTECTED'
    modes_checked = 0
    for modes in itertools.product(('AUTO', 'BYPASS', 'OFF'), repeat=8):
        for switches_on, protection_on, supply_fuse in itertools.product((False, True), repeat=3):
            live = reachable(graph(modes, switches_on, protection_on, supply_fuse, selector=selector))
            auto_live = switches_on and protection_on and supply_fuse
            for n, mode in enumerate(modes, 1):
                assert (f'LOAD{n}' in live) == (mode == 'BYPASS' or mode == 'AUTO' and auto_live)
            if not protection_on or not supply_fuse:
                assert 'AUTO_PROTECTED' not in live, ('BYPASS backfeed', modes)
            modes_checked += 1
    fault_cases = 0
    faults = ['protection_short', 'protected_ground', 'fused_input_ground']
    faults += [(n, kind) for n in range(1, 9)
               for kind in ('stuck_on', 'vs_ground', 'out_ground')]
    for fault in faults:
        for switches_on in (False, True):
            # Recovery: remove ONLY the shared AUTO feed fuse, move load fuses
            # to BYPASS. Include a shorted protector; software is not involved.
            live = reachable(graph(['BYPASS'] * 8, switches_on, True, False, fault, selector))
            assert all(f'LOAD{n}' in live for n in range(1, 9))
            assert 'AUTO_PROTECTED' not in live and 'FAULT_GND' not in live
            fault_cases += 1
    # Negative control: an accidental hard connection from a load to its
    # PROFET output must be detected, even with protection turned off.
    broken = graph(['BYPASS'] * 8, protection_on=False)
    broken.setdefault('LOAD1', set()).add('PROFET_OUT1')
    assert 'AUTO_PROTECTED' in reachable(broken)
    return dict(status='accepted_topology_model_only_not_implemented_in_saved_pcb',
                mode_cases=modes_checked, fault_recovery_cases=fault_cases,
                negative_control_detects_output_backfeed=True,
                exclusions=['fuse clearing/selectivity', 'semiconductor stress',
                            'parasitic and signal paths', 'transient response',
                            'PCB connectivity', 'thermal/current qualification'])


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
