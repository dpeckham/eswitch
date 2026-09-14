#!/usr/bin/env python3
"""Remove only legacy signal segments colliding with the new J3 hole pattern.

Run after DRC and before `just route`. The current report identifies the exact
segments; unrelated and power routing is preserved. Re-running after clean DRC
does nothing. This is an explicit migration, not a general DRC auto-fixer.
"""
import json
import os
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(ROOT, "eswitch.kicad_pcb")
with open(os.path.join(ROOT, "out", "drc.json")) as f:
    report = json.load(f)
ids = set()
for v in report["violations"]:
    if v["severity"] != "error" or not any("of J3" in i["description"] for i in v["items"]):
        continue
    for item in v["items"]:
        if item["description"].startswith(("Track ", "Via ")):
            ids.add(item["uuid"])
b = pcbnew.LoadBoard(path)
victims = [t for t in b.GetTracks() if t.m_Uuid.AsString() in ids]
for t in victims:
    assert t.GetNetname().startswith(("IN", "IS", "DEN", "+3V3")), t.GetNetname()
for t in victims:
    b.Remove(t)
pcbnew.SaveBoard(path, b)
print(f"Removed {len(victims)} colliding legacy signal segments/vias; reroute required")
