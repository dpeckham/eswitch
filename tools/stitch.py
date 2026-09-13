#!/usr/bin/env python3
"""Stand-alone pass: add vias to isolated outer-layer GND pour islands, refill, save."""
import os
import sys
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from route import stitch_islands  # noqa: E402
from gen_pcb import apply_rules, persist_project_rules  # noqa: E402

PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "eswitch.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
apply_rules(b)
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
n = stitch_islands(b)
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
persist_project_rules(PCB)
print("saved", PCB, "vias added:", n)
