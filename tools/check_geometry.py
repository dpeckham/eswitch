#!/usr/bin/env python3
"""Check stackup, antenna keepout and the saved USB reference-plane geometry.

These are layout checks, not current/thermal or signal-integrity qualification.
Run with KiCad Python after filling zones.
"""
import argparse
import json
import math
from pathlib import Path
import pcbnew
from gen_pcb import V
from sexp import parse_one, find, find_all

ROOT = Path(__file__).resolve().parent.parent


def check(path):
    board = pcbnew.LoadBoard(str(path))
    box = board.GetBoardEdgesBoundingBox()
    # KiCad includes the 0.05 mm outline stroke in this bounding box.
    assert abs(pcbnew.ToMM(box.GetWidth()) - 253) < .1
    assert abs(pcbnew.ToMM(box.GetHeight()) - 75) < .1
    assert board.GetCopperLayerCount() == 4
    doc = parse_one(path.read_text())
    stack = find(find(doc, "setup"), "stackup")
    assert stack is not None
    layers = {item[1]: item for item in find_all(stack, "layer")}
    for name, thickness in (("F.Cu", .07), ("In1.Cu", .061), ("In2.Cu", .061), ("B.Cu", .07)):
        assert abs(float(find(layers[name], "thickness")[1]) - thickness) < 1e-6, name
    assert find(stack, "copper_finish")[1] == "ENIG"
    assert not any(t.GetLayer() == pcbnew.In1_Cu and t.GetClass() == "PCB_TRACK"
                   and t.GetNetname() != "GND" for t in board.GetTracks()), "Signal cuts ground plane"
    module = board.FindFootprintByReference("U10")
    keepouts = [z for z in [*board.Zones(), *module.Zones()] if z.GetIsRuleArea()
                and z.GetDoNotAllowTracks() and z.GetDoNotAllowPads()
                and z.GetDoNotAllowVias() and z.GetDoNotAllowZoneFills()]
    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        for x, y in ((.1, .1), (35.9, .1), (.1, 1.8), (35.9, 1.8), (12, 1)):
            assert any(z.GetLayerSet().Contains(layer) and z.Outline().Contains(V(x, y))
                       for z in keepouts), "Antenna keepout missing or reduced"
    ground = [z.GetFilledPolysList(pcbnew.In2_Cu) for z in board.Zones()
              if not z.GetIsRuleArea() and z.GetNetname() == "GND"
              and z.GetLayerSet().Contains(pcbnew.In2_Cu)]
    usb = [t for t in board.GetTracks() if t.GetNetname().removeprefix("/")
           in ("USB_D+", "USB_D-", "USB_MCU_D+", "USB_MCU_D-")]
    assert usb, "USB routes missing"
    lengths = {}
    samples = 0
    for track in usb:
        assert track.GetClass() == "PCB_TRACK" and track.GetLayer() == pcbnew.B_Cu
        assert abs(pcbnew.ToMM(track.GetWidth()) - .235) < 1e-6
        a, b = track.GetStart(), track.GetEnd()
        ax, ay, bx, by = map(pcbnew.ToMM, (a.x, a.y, b.x, b.y))
        length = math.hypot(bx-ax, by-ay)
        lengths[track.GetNetname()] = lengths.get(track.GetNetname(), 0) + length
        if not length:
            continue
        steps = max(1, math.ceil(length/.1))
        for i in range(steps+1):
            for offset in (-.1175, 0, .1175):
                x = ax+(bx-ax)*i/steps-(by-ay)/length*offset
                y = ay+(by-ay)*i/steps+(bx-ax)/length*offset
                assert any(poly.Contains(V(x, y)) for poly in ground), (
                    "USB reference plane gap", track.GetNetname(), x, y)
                samples += 1
    result = dict(board_mm=[253, 75], copper_mm=[.07, .061, .061, .07],
                  antenna_keepout=True, usb_reference_samples=samples,
                  usb_track_lengths_mm=lengths,
                  limitation="Sampled reference coverage; not field-solver or hardware USB qualification")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=ROOT / "eswitch.kicad_pcb")
    check(parser.parse_args().board.resolve())
