#!/usr/bin/env python3
"""Screen selected JLCPCB dimensions; this is not a complete CAM/DFM review."""
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew
import wx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    app = wx.App(False)
    board = pcbnew.LoadBoard(str(args.board))
    mm = pcbnew.ToMM
    failures = []
    tracks = []
    vias = []
    pads = []
    for item in board.GetTracks():
        if item.GetClass() == 'PCB_TRACK':
            width = mm(item.GetWidth())
            tracks.append(width)
            if width < .16 - 1e-6:
                failures.append(dict(kind='track_width', uuid=item.m_Uuid.AsString(), width_mm=width))
        elif item.GetClass() == 'PCB_VIA':
            drill = mm(item.GetDrill())
            diameter = mm(item.GetWidth(pcbnew.F_Cu))
            vias.append((drill, diameter))
            if drill < .15 - 1e-6 or diameter - drill < .1 - 1e-6:
                failures.append(dict(kind='via_dimensions', uuid=item.m_Uuid.AsString(),
                                     drill_mm=drill, diameter_mm=diameter))
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
                continue
            size, drill = pad.GetSize(), pad.GetDrillSize()
            ring = min(mm(size.x - drill.x), mm(size.y - drill.y)) / 2
            entry = dict(ref=footprint.GetReference(), pad=pad.GetNumber(),
                         drill_mm=[mm(drill.x), mm(drill.y)], annular_ring_mm=ring)
            pads.append(entry)
            if ring < .254 - 1e-6:
                failures.append(dict(kind='pth_annular_ring', **entry))
    report = dict(
        status='selected_dimensions_pass' if not failures else 'selected_dimensions_fail',
        board_sha256=hashlib.sha256(args.board.read_bytes()).hexdigest(),
        source='https://jlcpcb.com/capabilities/pcb-capabilities',
        rules_checked_on='2026-10-26',
        copper='2 oz outer and inner, four layers',
        limits_mm=dict(track_width=.16, via_drill=.15, via_diameter_minus_drill=.1,
                       pth_annular_ring=.254),
        minimum_track_width_mm=min(tracks),
        via_drill_and_diameter_mm=sorted(set(vias)),
        minimum_pth_annular_ring_mm=min(p['annular_ring_mm'] for p in pads),
        pth_pad_count=len(pads),
        not_checked=['same-net gaps', 'mask webs', 'hole-to-copper and hole-to-hole spacing',
                     'legend readability', 'slot/routing tolerances', 'finished impedance',
                     'CAM acceptance', 'assembly process'],
        failures=failures,
    )
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
