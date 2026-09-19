#!/usr/bin/env python3
"""Repair signal gaps without ripping up other nets or crossing power pours.

Requires NumPy in KiCad's Python environment. Routes only nets named in the DRC
gap list, on F.Cu/In2.Cu/B.Cu (never the In1 GND plane). Every candidate is checked
by native DRC before replacing the working board; electrical/thermal review is
still required. This is not a power-stage or controlled-impedance router.
"""
import heapq
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
# NumPy is installed here by `just repair-gaps` because KiCad's embedded Python
# cannot reliably import distribution packages from the host site-packages.
sys.path.insert(0, str(ROOT / "out" / "py311"))
import numpy as np
import pcbnew

from gen_pcb import V, W, H, apply_rules
from pcb_nets import short_name
from pcb_io import save_board, fill_zones

PCB = ROOT / "eswitch.kicad_pcb"
CANDIDATE = ROOT / "out/route-candidate.kicad_pcb"
REPORT = ROOT / "out/route-gaps-drc.json"
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
STEP = 0.1
GUARD = 0.025
NX, NY = round(W / STEP) + 1, round(H / STEP) + 1
SIZE = NX * NY
mm = pcbnew.ToMM


def xy(point):
    return mm(point.x), mm(point.y)


class Raster:
    def __init__(self):
        self.data = np.zeros((NY, NX), dtype=np.bool_)

    def window(self, x0, y0, x1, y1):
        i0, i1 = max(0, math.floor(x0 / STEP)), min(NX - 1, math.ceil(x1 / STEP))
        j0, j1 = max(0, math.floor(y0 / STEP)), min(NY - 1, math.ceil(y1 / STEP))
        if i0 > i1 or j0 > j1:
            return None
        xx, yy = np.meshgrid(np.arange(i0, i1 + 1) * STEP, np.arange(j0, j1 + 1) * STEP)
        return self.data[j0:j1 + 1, i0:i1 + 1], xx, yy

    def segment(self, start, end, radius):
        ax, ay = start
        bx, by = end
        window = self.window(min(ax, bx) - radius, min(ay, by) - radius,
                             max(ax, bx) + radius, max(ay, by) + radius)
        if window is None:
            return
        target, xx, yy = window
        length2 = (bx - ax) ** 2 + (by - ay) ** 2
        fraction = np.clip(((xx - ax) * (bx - ax) + (yy - ay) * (by - ay)) / length2, 0, 1) if length2 else 0
        target |= (xx - ax - fraction * (bx - ax)) ** 2 + (yy - ay - fraction * (by - ay)) ** 2 <= radius ** 2

    def polygon(self, points, clearance=0):
        if len(points) < 3:
            return
        px, py = zip(*points)
        window = self.window(min(px), min(py), max(px), max(py))
        if window is not None:
            target, xx, yy = window
            inside = np.zeros(xx.shape, dtype=np.bool_)
            for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
                if ay != by:
                    inside ^= ((ay > yy) != (by > yy)) & (xx < (bx - ax) * (yy - ay) / (by - ay) + ax)
            target |= inside
        if clearance:
            for a, b in zip(points, points[1:] + points[:1]):
                self.segment(a, b, clearance)

    def edge(self, margin):
        self.data[:, np.arange(NX) * STEP < margin] = True
        self.data[:, np.arange(NX) * STEP > W - margin] = True
        self.data[np.arange(NY) * STEP < margin, :] = True
        self.data[np.arange(NY) * STEP > H - margin, :] = True


def polygons(polyset):
    return [[xy(outline.CPoint(i)) for i in range(outline.PointCount())]
            for outline in (polyset.COutline(j) for j in range(polyset.OutlineCount()))]


def pad_polygons(pad, layer):
    shape = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(shape, layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_OUTSIDE)
    return polygons(shape)


def obstacles(board, code, width, diameter):
    half = width / 2 + 0.2 + GUARD
    via_radius = diameter / 2 + 0.2 + GUARD
    layers = {layer: Raster() for layer in LAYERS}
    via = Raster()
    for track in board.GetTracks():
        is_via = track.GetClass() == "PCB_VIA"
        start, end = xy(track.GetStart()), xy(track.GetEnd())
        if is_via:
            start = end = xy(track.GetPosition())
        size = mm(track.GetWidth(pcbnew.F_Cu) if is_via else track.GetWidth()) / 2
        if track.GetNetCode() != code:
            for layer, raster in layers.items():
                if is_via or track.GetLayer() == layer:
                    raster.segment(start, end, size + half)
            via.segment(start, end, size + via_radius)
        elif is_via:
            # Avoid duplicate/co-located holes. Existing same-net vias are usable
            # as source/target anchors, so no new via is needed at those points.
            via.segment(start, end, mm(track.GetDrill()) / 2 + diameter / 2 + 0.25)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                radius = max(mm(pad.GetDrillSize().x), mm(pad.GetDrillSize().y)) / 2
                for raster in layers.values():
                    raster.segment(xy(pad.GetPosition()), xy(pad.GetPosition()), radius + half)
                via.segment(xy(pad.GetPosition()), xy(pad.GetPosition()), radius + via_radius)
            elif pad.GetNetCode() != code:
                for layer, raster in layers.items():
                    if pad.IsOnLayer(layer):
                        for polygon in pad_polygons(pad, layer):
                            raster.polygon(polygon, half)
                # A through via crosses all copper layers, including In1.Cu.
                for layer in [*LAYERS, pcbnew.In1_Cu]:
                    if pad.IsOnLayer(layer):
                        for polygon in pad_polygons(pad, layer):
                            via.polygon(polygon, via_radius)
            elif pad.GetDrillSize().x:
                radius = max(mm(pad.GetDrillSize().x), mm(pad.GetDrillSize().y)) / 2
                via.segment(xy(pad.GetPosition()), xy(pad.GetPosition()), radius + diameter / 2 + 0.25)
    zones = list(board.Zones()) + [zone for fp in board.GetFootprints() for zone in fp.Zones()]
    for zone in zones:
        rule = zone.GetIsRuleArea()
        if not rule and (zone.GetNetCode() == code or short_name(zone) == "GND"):
            continue
        for polygon in polygons(zone.Outline()):
            if not rule or zone.GetDoNotAllowTracks():
                for layer, raster in layers.items():
                    if zone.IsOnLayer(layer):
                        raster.polygon(polygon, half)
            # A sparse signal via is allowed through the broad power spreaders.
            # KiCad clears it from foreign pours. Tracks still cannot cut a pour.
            if rule and (zone.GetDoNotAllowVias() or zone.GetZoneName().startswith("usb_reference_")):
                via.polygon(polygon, via_radius)
    for raster in layers.values():
        raster.edge(0.4 + width / 2 + GUARD)
    via.edge(0.4 + diameter / 2 + GUARD)
    return np.stack([layers[layer].data for layer in LAYERS]).reshape(-1), via.data.reshape(-1)


def component(board, item):
    conn = board.GetConnectivity()
    found, pending = {}, [item]
    while pending:
        current = pending.pop()
        key = current.m_Uuid.AsString()
        if key in found:
            continue
        found[key] = current
        pending.extend(conn.GetConnectedTracks(current))
        pending.extend(conn.GetConnectedPads(current))
    return list(found.values())


def anchors(items, blocked):
    result = {}
    for item in items:
        if item.GetClass() == "PCB_TRACK":
            ax, ay = xy(item.GetStart())
            bx, by = xy(item.GetEnd())
            length = math.hypot(ax - bx, ay - by)
            steps = max(1, math.ceil(length / 0.5))
            points = [(ax + (bx - ax) * k / steps, ay + (by - ay) * k / steps) for k in range(steps + 1)]
        else:
            points = [xy(item.GetPosition())]
        for layer_index, layer in enumerate(LAYERS):
            if not item.IsOnLayer(layer):
                continue
            for x, y in points:
                i, j = round(x / STEP), round(y / STEP)
                if not (0 <= i < NX and 0 <= j < NY):
                    continue
                node = layer_index * SIZE + j * NX + i
                if not blocked[node]:
                    result[node] = (x, y)
    return result


def search(blocked, via_blocked, starts, goals):
    # Euclidean distance to the closest target bounding rectangle is admissible.
    target_xy = [(node % SIZE % NX, node % SIZE // NX) for node in goals]
    x0, y0 = map(min, zip(*target_xy))
    x1, y1 = map(max, zip(*target_xy))

    def estimate(node):
        i, j = node % SIZE % NX, node % SIZE // NX
        return max(x0 - i, 0, i - x1) + max(y0 - j, 0, j - y1)

    distance = np.full(3 * SIZE, np.inf)
    parent = np.full(3 * SIZE, -1, dtype=np.int32)
    queue = []
    for start in starts:
        distance[start] = 0
        heapq.heappush(queue, (estimate(start), 0.0, start))
    visited = 0
    while queue:
        _, cost, node = heapq.heappop(queue)
        if cost > distance[node]:
            continue
        visited += 1
        if node in goals:
            path = [node]
            while parent[path[-1]] != -1:
                path.append(int(parent[path[-1]]))
            print(f"  search visited {visited} nodes", flush=True)
            return path[::-1]
        plane, location = divmod(node, SIZE)
        row, column = divmod(location, NX)
        neighbors = []
        if column:
            neighbors.append((node - 1, 1))
        if column + 1 < NX:
            neighbors.append((node + 1, 1))
        if row:
            neighbors.append((node - NX, 1))
        if row + 1 < NY:
            neighbors.append((node + NX, 1))
        if not via_blocked[location]:
            neighbors.extend((other * SIZE + location, 35) for other in range(3) if other != plane)
        for nxt, delta in neighbors:
            new_cost = cost + delta
            if not blocked[nxt] and new_cost < distance[nxt]:
                distance[nxt] = new_cost
                parent[nxt] = node
                heapq.heappush(queue, (new_cost + estimate(nxt), new_cost, nxt))
    print(f"  no path after {visited} nodes", flush=True)
    return None


def add_route(board, net, path, starts, goals, width, diameter, drill):
    def point(node):
        location = node % SIZE
        return location % NX * STEP, location // NX * STEP

    def track(a, b, layer):
        if math.dist(a, b) < 0.00001:
            return
        item = pcbnew.PCB_TRACK(board)
        item.SetStart(V(*a))
        item.SetEnd(V(*b))
        item.SetLayer(layer)
        item.SetWidth(pcbnew.FromMM(width))
        item.SetNet(net)
        board.Add(item)

    track(starts[path[0]], point(path[0]), LAYERS[path[0] // SIZE])
    start = path[0]
    previous_direction = None
    vias = set()
    for a, b in zip(path, path[1:]):
        direction = b - a
        if direction != previous_direction or a // SIZE != b // SIZE:
            track(point(start), point(a), LAYERS[a // SIZE])
            start = a
        if a // SIZE != b // SIZE:
            location = a % SIZE
            if location not in vias:
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(V(*point(a)))
                via.SetWidth(pcbnew.FromMM(diameter))
                via.SetDrill(pcbnew.FromMM(drill))
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                via.SetNet(net)
                board.Add(via)
                vias.add(location)
            start = b
        previous_direction = direction
    track(point(start), point(path[-1]), LAYERS[path[-1] // SIZE])
    track(point(path[-1]), goals[path[-1]], LAYERS[path[-1] // SIZE])
    print(f"  added route with {len(vias)} vias", flush=True)


def drc(board):
    fill_zones(board)
    save_board(CANDIDATE, board)
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json",
                    "-o", str(REPORT), str(CANDIDATE)], cwd=ROOT, check=True, capture_output=True)
    return json.loads(REPORT.read_text())


def main():
    global PCB, CANDIDATE, REPORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=PCB,
                        help="Working board to repair; defaults to the tracked PCB")
    args = parser.parse_args()
    PCB = args.board.resolve()
    CANDIDATE = ROOT / "out" / f"{PCB.stem}-route-candidate.kicad_pcb"
    REPORT = ROOT / "out" / f"{PCB.stem}-route-drc.json"
    shutil.copyfile(PCB.with_suffix(".kicad_pro"), CANDIDATE.with_suffix(".kicad_pro"))
    board = pcbnew.LoadBoard(str(PCB))
    apply_rules(board)
    report = drc(board)
    assert not any(v["severity"] == "error" for v in report["violations"]), "Resolve existing copper errors first"
    failed = set()
    def signal_gaps(result):
        # Routing can divide an outer GND pour into islands. Those still must be
        # stitched before release, but must not hide genuine signal progress.
        return sum(not all("[GND]" in i["description"] for i in gap["items"])
                   for gap in result["unconnected_items"])
    for attempt in range(100):
        if not report["unconnected_items"]:
            break
        progress = False
        for gap in report["unconnected_items"]:
            key = tuple(sorted(item["uuid"] for item in gap["items"]))
            if key in failed:
                continue
            # A rejected candidate reloads the board. Do not reuse SWIG pointers
            # into the previous board when considering the next gap.
            items = {item.m_Uuid.AsString(): item for item in board.GetTracks()}
            items.update({pad.m_Uuid.AsString(): pad for fp in board.GetFootprints() for pad in fp.Pads()})
            if any(item["uuid"] not in items for item in gap["items"]):
                continue  # ground-plane island stitching is a separate step
            a, b = [items[item["uuid"]] for item in gap["items"]]
            name = short_name(a)
            assert a.GetNetCode() == b.GetNetCode()
            if name == "GND":
                continue  # Ground connections require separate reviewed stitching.
            assert name.startswith(("IN", "IS", "DEN", "UGND", "+3V3")), f"Not a permitted signal repair: {name}"
            print(f"Routing {name}; {len(report['unconnected_items'])} gaps remain", flush=True)
            width, diameter, drill = (0.5, 0.8, 0.4) if name == "+3V3" else (0.25, 0.6, 0.3)
            blocked, via_blocked = obstacles(board, a.GetNetCode(), width, diameter)
            starts = anchors(component(board, a), blocked)
            goals = anchors(component(board, b), blocked)
            print(f"  anchors {len(starts)} -> {len(goals)}", flush=True)
            if not starts or not goals:
                failed.add(key)
                continue
            path = search(blocked, via_blocked, starts, goals)
            if path is None:
                failed.add(key)
                continue
            add_route(board, a.GetNet(), path, starts, goals, width, diameter, drill)
            candidate_report = drc(board)
            errors = [v for v in candidate_report["violations"] if v["severity"] == "error"]
            if errors or signal_gaps(candidate_report) >= signal_gaps(report):
                print("Candidate rejected; original board preserved:", errors[:2], flush=True)
                board = pcbnew.LoadBoard(str(PCB))
                apply_rules(board)
                failed.add(key)
                continue
            save_board(PCB, board)
            print("  DRC accepted; saved", flush=True)
            board = pcbnew.LoadBoard(str(PCB))
            apply_rules(board)
            report = candidate_report
            progress = True
            break
        if not progress:
            break
    print("Remaining gaps:", len(report["unconnected_items"]), flush=True)


if __name__ == "__main__":
    main()
