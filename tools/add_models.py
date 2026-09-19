#!/usr/bin/env python3
"""Refresh 3D model references of the project-library footprints on an existing board.

Run with `kicad python3.11 tools/add_models.py` after changing lib/eswitch.pretty models,
so the routed board picks them up without regenerating (and losing) the routing.
"""
import os
import pcbnew
from pcb_io import save_board

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "eswitch.kicad_pcb")
LIB = os.path.join(ROOT, "lib", "eswitch.pretty")

b = pcbnew.LoadBoard(PCB)
n = 0
for fp in b.GetFootprints():
    name = str(fp.GetFPID().GetLibItemName())
    if not os.path.exists(os.path.join(LIB, name + ".kicad_mod")):
        continue
    src = pcbnew.FootprintLoad(LIB, name)
    models = fp.Models()
    models.clear()
    for m in src.Models():
        models.push_back(m)
    n += 1
save_board(PCB, b)
print("updated models on", n, "footprints")
