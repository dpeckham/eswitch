#!/usr/bin/env python3
"""Compare physical pad assignments with the exported single-sheet schematic.

The legacy PCB generator removes the root '/' from local net names. Normalize
only that prefix here; this is NOT a waiver of native KiCad parity warnings or a
test of actual track/zone connectivity (DRC must check the latter).
"""
from pathlib import Path
import pcbnew

from sexp import parse_one, find, find_all

ROOT = Path(__file__).resolve().parent.parent


def main():
    doc = parse_one((ROOT / "out/eswitch.net").read_text())
    assert len(find_all(find(doc, "design"), "sheet")) == 1, "Normalization requires one root sheet"
    components = {find(c, "ref")[1]: c for c in find_all(find(doc, "components"), "comp")
                  if find(c, "footprint")}
    expected = {}
    for net in find_all(find(doc, "nets"), "net"):
        name = find(net, "name")[1].removeprefix("/")
        for node in find_all(net, "node"):
            ref, pin = find(node, "ref")[1], str(find(node, "pin")[1])
            if ref in components:
                expected[ref, pin] = name
    board = pcbnew.LoadBoard(str(ROOT / "eswitch.kicad_pcb"))
    actual = {}
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    assert footprints.keys() == components.keys(), "PCB/schematic component references differ"
    for ref, fp in footprints.items():
        component = components[ref]
        assert fp.GetValue() == find(component, "value")[1], (ref, "value")
        assert str(fp.GetFPID().GetLibItemName()) == find(component, "footprint")[1].split(":")[1], (ref, "footprint")
        for pad in fp.Pads():
            key = ref, pad.GetNumber()
            name = pad.GetNetname().removeprefix("/")
            if key in actual:
                assert actual[key] == name, (key, "duplicate physical pads disagree")
            if pad.GetNumber():
                actual[key] = name
    for key, name in expected.items():
        assert key in actual, (key, "missing physical pad")
        if name.startswith("unconnected-") and not actual[key]:
            continue  # Explicit schematic NC may be an unassigned physical pad.
        assert actual[key] == name, (key, "PCB", actual[key], "schematic", name)
    for key, name in actual.items():
        assert key in expected or not name, (key, "unexpected pad net", name)
    print(f"PCB pad assignments match schematic ({len(expected)} pins, root '/' normalized)")
    print("Native parity metadata/naming warnings and unrouted copper remain separate release checks")


if __name__ == "__main__":
    main()
