#!/usr/bin/env python3
"""Stitch isolated GND pours, accepting each via only after native DRC.

Uses the signal router's geometric clearance masks. A sparse stitch may clear
the F.Cu VS thermal spreader; it may not pierce the main power buses, channel
current strips or USB reference corridor. Requires KiCad Python/NumPy.
"""
import argparse
import json
import math
from pathlib import Path
import shutil

import pcbnew
import route_gaps as router
from gen_pcb import V, apply_rules
from pcb_io import save_board


def ground_gaps(report):
    return sum(all("[GND]" in item["description"] for item in gap["items"])
               for gap in report["unconnected_items"])


def proposals(board,limit_per_island=5):
    """Find interior sites on islands with no existing through connection."""
    ground = board.FindNet("GND")
    _, blocked = router.obstacles(board, ground.GetNetCode(), .25, .6)
    # The outer GND islands sit underneath F.Cu thermal spreaders. Allow one
    # clearance hole there while preserving the B.Cu feed and In2 CH8 strip.
    power = router.Raster()
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetNetCode() == ground.GetNetCode():
            continue
        if zone.GetLayer() == pcbnew.F_Cu and zone.GetNetname().removeprefix("/").startswith("VS"):
            continue
        for points in router.polygons(zone.Outline()):
            power.polygon(points, .5)
    blocked |= power.data.reshape(-1)
    terminals = [router.xy(t.GetPosition()) for t in board.GetTracks()
                 if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    terminals += [router.xy(p.GetPosition()) for fp in board.GetFootprints() for p in fp.Pads()
                  if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetNetname() != "GND" or zone.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
            continue
        filled = zone.GetFilledPolysList(zone.GetLayer())
        for index in range(filled.OutlineCount()):
            outline = filled.COutline(index)
            if any(filled.Contains(V(x, y), index) for x, y in terminals):
                continue
            box = outline.BBox()
            x0, y0 = router.xy(box.GetPosition())
            x1, y1 = router.xy(box.GetEnd())
            best = []
            for ix in range(round(x0 * 4), round(x1 * 4) + 1):
                for iy in range(round(y0 * 4), round(y1 * 4) + 1):
                    x, y = ix / 4, iy / 4
                    i, j = round(x / router.STEP), round(y / router.STEP)
                    if not (0 <= i < router.NX and 0 <= j < router.NY) or blocked[j * router.NX + i]:
                        continue
                    point = V(x, y)
                    if not filled.Contains(point, index):
                        continue
                    distance = pcbnew.ToMM(outline.Distance(point, True))
                    if distance >= .4:
                        best.append((distance, x, y))
            # Limit native DRC trials per island; never force a marginal site.
            for _, x, y in sorted(best, reverse=True)[:limit_per_island]:
                yield x, y


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=router.PCB)
    args = parser.parse_args()
    path = args.board.resolve()
    router.CANDIDATE = router.ROOT / "out" / f"{path.stem}-stitch-candidate.kicad_pcb"
    router.REPORT = router.ROOT / "out" / f"{path.stem}-stitch-drc.json"
    shutil.copyfile(path.with_suffix(".kicad_pro"), router.CANDIDATE.with_suffix(".kicad_pro"))
    board = pcbnew.LoadBoard(str(path))
    apply_rules(board)
    report = router.drc(board)
    assert not any(v["severity"] == "error" for v in report["violations"])
    added = []
    while ground_gaps(report):
        # One interior point per isolated pour can be checked as a transaction.
        # Every via still undergoes the full native clearance/connectivity check.
        points=[]
        for p in proposals(board,1):
            if all(math.dist(p,q)>.7 for q in points):points.append(p)
        if len(points)>1:
            for x,y in points:
                via=pcbnew.PCB_VIA(board);via.SetPosition(V(x,y));via.SetWidth(pcbnew.FromMM(.6))
                via.SetDrill(pcbnew.FromMM(.3));via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
                via.SetNet(board.FindNet('GND'));board.Add(via)
            after=router.drc(board)
            if not any(v['severity']=='error' for v in after['violations']) and ground_gaps(after)<ground_gaps(report) and len(after['unconnected_items'])<len(report['unconnected_items']):
                save_board(path,board);report=after;added.extend(points)
                print(f'Accepted {len(points)} GND stitches; {ground_gaps(report)} ground gaps remain',flush=True)
                board=pcbnew.LoadBoard(str(path));apply_rules(board)
                continue
            print('GND group rejected; retrying individual sites',flush=True)
            board=pcbnew.LoadBoard(str(path));apply_rules(board)
        candidates = list(proposals(board))
        for x, y in candidates:
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(V(x, y))
            via.SetWidth(pcbnew.FromMM(.6))
            via.SetDrill(pcbnew.FromMM(.3))
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            via.SetNet(board.FindNet("GND"))
            board.Add(via)
            after = router.drc(board)
            errors = [v for v in after["violations"] if v["severity"] == "error"]
            if not errors and ground_gaps(after) < ground_gaps(report) and len(after["unconnected_items"]) < len(report["unconnected_items"]):
                save_board(path, board)
                report = after
                added.append((x, y))
                print(f"Accepted GND via {(x, y)}; {ground_gaps(report)} ground gaps remain", flush=True)
                board = pcbnew.LoadBoard(str(path))
                apply_rules(board)
                break
            board = pcbnew.LoadBoard(str(path))
            apply_rules(board)
        else:
            break
    print(json.dumps(dict(added=added, remaining_ground_gaps=ground_gaps(report))), flush=True)


if __name__ == "__main__":
    main()
