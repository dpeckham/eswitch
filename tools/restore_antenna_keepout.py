#!/usr/bin/env python3
"""One-time routed-board migration for the ESP32 antenna keepout.

KiCad 10 invalidates Python wrappers after some BOARD.Remove() calls, so the
migration is deliberately split into processes: move, ripup, route, then zone.
The generator retains the library keepout for boards regenerated from scratch.
"""
import sys
from pathlib import Path

import pcbnew

from gen_pcb import V
from pcb_nets import find_net, short_name

PCB = Path(__file__).resolve().parent.parent / "eswitch.kicad_pcb"


def xy(point):
    return pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)


def add_track(board, netname, layer, points, width=0.6):
    net = find_net(board, netname)
    for start, end in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(V(*start))
        track.SetEnd(V(*end))
        track.SetLayer(layer)
        track.SetWidth(pcbnew.FromMM(width))
        track.SetNet(net)
        board.Add(track)


def move():
    board = pcbnew.LoadBoard(PCB)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref, x, y, angle in (
        ("C10", 23.4, 4.6, 0.0),
        ("C1", 28.5, 3.48, 180.0),
        ("C2", 34.5, 3.48, 180.0),
    ):
        footprints[ref].SetOrientationDegrees(angle)
        footprints[ref].SetPosition(V(x, y))
    footprints["U9"].Reference().SetVisible(False)
    pcbnew.SaveBoard(PCB, board)


def ripup():
    board = pcbnew.LoadBoard(PCB)
    victims = []
    for track in board.GetTracks():
        name = short_name(track)
        if track.GetClass() == "PCB_VIA":
            x, y = xy(track.GetPosition())
            if name == "VIN" and x > 36.0 and y < 8.5:
                victims.append(track)
            continue
        starts = xy(track.GetStart())
        ends = xy(track.GetEnd())
        xs, ys = zip(starts, ends)
        if (name == "VIN" and min(xs) >= 28.0 and max(xs) <= 38.0
                and min(ys) < 8.5 and track.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)):
            victims.append(track)
        elif (name == "+3V3" and track.GetLayer() == pcbnew.B_Cu
              and min(xs) >= 20.7 and max(xs) <= 25.0 and min(ys) < 4.7):
            victims.append(track)
        elif (name == "GND" and track.GetLayer() == pcbnew.B_Cu
              and min(xs) >= 20.0 and max(xs) <= 36.0 and min(ys) < 6.5):
            victims.append(track)
    victims.extend(zone for zone in board.Zones()
                   if zone.GetIsRuleArea() and zone.GetZoneName() == "ESP32_ANTENNA_KEEPOUT")
    for item in victims:
        board.Remove(item)
    pcbnew.SaveBoard(PCB, board)
    print(f"removed {len(victims)} obsolete antenna-area items")


def route():
    board = pcbnew.LoadBoard(PCB)
    add_track(board, "+3V3", pcbnew.B_Cu, [(20.75, 4.61), (22.625, 4.6)])
    add_track(board, "VIN", pcbnew.B_Cu, [(28.598, 2.466), (29.975, 3.48)])

    # A top-side link avoids the BOOT net while joining the input capacitors to
    # the compact U9/C3 VIN connection on the bottom side.
    add_track(board, "VIN", pcbnew.F_Cu,
              [(28.598, 2.466), (37.0, 2.466), (37.0, 7.556)])
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(V(37.0, 7.556))
    via.SetDrill(pcbnew.FromMM(0.4))
    via.SetWidth(pcbnew.FromMM(0.9))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(find_net(board, "VIN"))
    board.Add(via)
    add_track(board, "VIN", pcbnew.B_Cu,
              [(35.975, 3.48), (37.0, 4.505), (37.0, 7.556),
               (35.469, 7.556), (34.8, 8.225), (33.917, 8.225),
               (33.777, 8.365), (32.5, 8.365)])
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB, board)


def zone():
    board = pcbnew.LoadBoard(PCB)
    keepout = pcbnew.ZONE(board)
    keepout.SetIsRuleArea(True)
    keepout.SetZoneName("ESP32_ANTENNA_KEEPOUT")
    layers = pcbnew.LSET.AllCuMask()
    keepout.SetLayerSet(layers)
    keepout.SetDoNotAllowTracks(True)
    keepout.SetDoNotAllowVias(True)
    keepout.SetDoNotAllowPads(True)
    keepout.SetDoNotAllowZoneFills(True)
    keepout.SetDoNotAllowFootprints(False)
    keepout.AddPolygon(pcbnew.VECTOR_VECTOR2I(
        [V(0, 0), V(36, 0), V(36, 1.85), V(0, 1.85)]))
    board.Add(keepout)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)


if __name__ == "__main__":
    phases = {"move": move, "ripup": ripup, "route": route, "zone": zone}
    if len(sys.argv) != 2 or sys.argv[1] not in phases:
        raise SystemExit(f"usage: {sys.argv[0]} " + "|".join(phases))
    phases[sys.argv[1]]()
