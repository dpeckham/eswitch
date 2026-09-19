#!/usr/bin/env python3
"""Remove DRC-identified dangling tracks/vias only if connectivity is preserved."""
import argparse
from pathlib import Path
import shutil
import re
from collections import defaultdict

import pcbnew
import route_gaps as router
from gen_pcb import apply_rules
from pcb_io import save_board
from sexp import parse_one, find, dump


def centerline_intersections(track, other):
    """Parameters along track where another same-layer segment joins it."""
    if other.GetClass() != "PCB_TRACK" or other.GetLayer() != track.GetLayer():
        return []
    a, b, c, d = track.GetStart(), track.GetEnd(), other.GetStart(), other.GetEnd()
    ax, ay, bx, by, cx, cy, dx, dy = a.x, a.y, b.x, b.y, c.x, c.y, d.x, d.y
    rx, ry, sx, sy = bx-ax, by-ay, dx-cx, dy-cy
    cross = rx*sy-ry*sx
    if cross:
        t, u = ((cx-ax)*sy-(cy-ay)*sx)/cross, ((cx-ax)*ry-(cy-ay)*rx)/cross
        return [max(0, min(1, t))] if -1e-7 <= t <= 1+1e-7 and -1e-7 <= u <= 1+1e-7 else []
    if (cx-ax)*ry-(cy-ay)*rx or not rx*rx+ry*ry:
        return []
    values = [((x-ax)*rx+(y-ay)*ry)/(rx*rx+ry*ry) for x,y in ((cx,cy),(dx,dy))]
    return [max(0, min(1, t)) for t in values if -1e-7 <= t <= 1+1e-7]


def expand_chains(doc, seeds, board):
    """Remove a dangling raster chain in one trial, stopping at branches/pads/vias.

    This is only a proposal. Native DRC must still prove unchanged connectivity;
    copper touching the middle of a segment can invalidate an endpoint graph.
    """
    tracks, nodes = {}, defaultdict(set)
    conn = board.GetConnectivity()
    junctions = {t.m_Uuid.AsString() for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"
                 and any(1e-7 < v < 1-1e-7 for n in conn.GetConnectedTracks(t)
                         for v in centerline_intersections(t, n))}
    for item in doc:
        if not isinstance(item, list) or item[0] != "segment":
            continue
        uid = find(item, "uuid")[1]
        keys = [(find(item, "net")[1], find(item, "layer")[1],
                 tuple(round(float(v)*1e6) for v in find(item, key)[1:3]))
                for key in ("start", "end")]
        tracks[uid] = keys
        for key in keys:
            nodes[key].add(uid)
    vias = {(v.GetNetname(), (v.GetPosition().x, v.GetPosition().y))
            for v in board.GetTracks() if v.GetClass() == "PCB_VIA"}
    pads = defaultdict(list)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pads[pad.GetNetname()].append(pad)

    def anchored(key):
        net, layer, point = key
        return ((net, point) in vias or any(p.IsOnLayer(board.GetLayerID(layer))
                and p.HitTest(pcbnew.VECTOR2I(*point)) for p in pads[net]))

    remove = dict.fromkeys(sorted(seeds))
    for uid in sorted(seeds):
        if uid not in tracks:
            continue
        ends = tracks[uid]
        leaves = [key for key in ends if len(nodes[key]) == 1 and not anchored(key)]
        if not leaves:
            continue
        previous, current = uid, next(key for key in ends if key != leaves[0])
        while len(nodes[current]) == 2 and not anchored(current):
            following = next(u for u in nodes[current] if u != previous)
            if following in remove or following in junctions:
                break
            remove[following] = None
            previous, current = following, next(key for key in tracks[following] if key != current)
    return list(remove)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=router.PCB)
    parser.add_argument("--max-passes", type=int, default=200,
                        help="Guarded passes; raster routes can have many short dangling segments")
    args = parser.parse_args()
    path = args.board.resolve()
    router.CANDIDATE = router.ROOT / "out" / f"{path.stem}-prune-candidate.kicad_pcb"
    router.REPORT = router.ROOT / "out" / f"{path.stem}-prune-drc.json"
    serialized_path = router.CANDIDATE.with_name("prune-input.kicad_pcb")
    for target in (router.CANDIDATE, serialized_path):
        shutil.copyfile(path.with_suffix(".kicad_pro"), target.with_suffix(".kicad_pro"))
    board = pcbnew.LoadBoard(str(path))
    apply_rules(board)
    report = router.drc(board)
    assert not any(v["severity"] == "error" for v in report["violations"])
    protected = set()
    for attempt in range(args.max_passes):
        remove = {item["uuid"] for v in report["violations"]
                  if v["type"] in ("track_dangling", "via_dangling") for item in v["items"]}
        remove -= protected
        if not remove:
            break
        # Avoid ownership changes of large sets of live SWIG objects.
        doc = parse_one(path.read_text())
        proposed = [uid for uid in expand_chains(doc, remove, board) if uid not in protected]
        remove = set(proposed)
        updated = [item for item in doc if not (isinstance(item, list) and item[0] in ("segment", "via")
                   and find(item, "uuid")[1] in remove)]
        count = len(doc)-len(updated)
        assert count == len(remove), "DRC does not describe this saved board"
        serialized_path.write_text(dump(updated)+"\n")
        candidate = pcbnew.LoadBoard(str(serialized_path))
        apply_rules(candidate)
        after = router.drc(candidate)
        if len(after["unconnected_items"]) > len(report["unconnected_items"]) and len(proposed) > 12:
            # Locate the last safe prefix instead of protecting an entire long
            # raster chain because its final segment also bridges live copper.
            lo, hi, accepted = 0, len(proposed), None
            while hi-lo > 1:
                mid = (lo+hi)//2
                trial_remove = set(proposed[:mid])
                trial = [item for item in doc if not (isinstance(item, list)
                         and item[0] in ("segment", "via") and find(item, "uuid")[1] in trial_remove)]
                serialized_path.write_text(dump(trial)+"\n")
                trial_board = pcbnew.LoadBoard(str(serialized_path))
                apply_rules(trial_board)
                trial_report = router.drc(trial_board)
                if (not any(v["severity"] == "error" for v in trial_report["violations"])
                        and len(trial_report["unconnected_items"]) <= len(report["unconnected_items"])):
                    lo, accepted = mid, (trial_board, trial_report)
                else:
                    hi = mid
            if accepted:
                candidate, after = accepted
                remove, count = set(proposed[:lo]), lo
        if any(v["severity"] == "error" for v in after["violations"]):
            raise SystemExit("Pruning rejected: DRC/connectivity regressed; last accepted board preserved")
        if len(after["unconnected_items"]) > len(report["unconnected_items"]):
            # A via connected on one layer can still bridge two offset track
            # endpoints on that layer. Preserve affected nets, then retry only
            # the independent removals; never accept that disconnected result.
            affected = {match for gap in after["unconnected_items"] for item in gap["items"]
                        for match in re.findall(r"\[([^]]+)\]", item["description"])}
            keep = {find(item, "uuid")[1] for item in doc
                    if isinstance(item, list) and item[0] in ("segment", "via")
                    and find(item, "uuid")[1] in remove and find(item, "net")[1] in affected}
            if not keep:
                raise SystemExit("Pruning rejected: unexplained connectivity change; original preserved")
            protected.update(keep)
            print(f"Preserving {len(keep)} items on {sorted(affected)} to retain connections", flush=True)
            continue
        save_board(path, candidate)
        board = candidate
        report = after
        print(f"Removed {count} dangling items; {len(report['unconnected_items'])} gaps", flush=True)
    else:
        raise SystemExit(f"Dangling cleanup needs further review after {args.max_passes} passes")


if __name__ == "__main__":
    main()
