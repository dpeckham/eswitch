#!/usr/bin/env python3
"""Auto-route signal nets with freerouting, then import the session and refill zones.

Run with KiCad's python: `kicad python3.11 tools/route.py [passes]`.
"""
import os
import subprocess
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "eswitch.kicad_pcb")
DSN = os.path.join(ROOT, "out", "eswitch.dsn")
SES = os.path.join(ROOT, "out", "eswitch.ses")
JAR = os.path.expanduser("~/.local/share/freerouting/freerouting-2.4.1.jar")


def main():
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from gen_pcb import apply_rules
    b = pcbnew.LoadBoard(PCB)
    apply_rules(b)
    if os.path.exists(SES):
        os.remove(SES)
    # Hide the outer GND pours while routing so freerouting drops real vias to the GND plane
    # for every GND pad instead of assuming the pour connects them.
    hidden = [z for z in b.Zones() if z.GetNetname() == "GND" and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
    for z in hidden:
        b.Remove(z)
    # Temporary keep-out rule areas over every explicit power zone (VS*, LOAD*, +12V) so the
    # router cannot cut them with foreign tracks or vias. Removed again after import.
    keepouts = []
    for z in list(b.Zones()):
        if z.GetNetname().startswith(("VS", "LOAD", "+12V")):
            k = pcbnew.ZONE(b)
            k.SetIsRuleArea(True)
            k.SetDoNotAllowTracks(True)
            k.SetDoNotAllowVias(True)
            k.SetDoNotAllowZoneFills(False)
            k.SetLayer(z.GetLayer())
            outline = z.Outline().COutline(0)
            pts = pcbnew.VECTOR_VECTOR2I([outline.CPoint(i) for i in range(outline.PointCount())])
            k.AddPolygon(pts)
            k.SetZoneName("tmp_keepout_" + z.GetZoneName())
            b.Add(k)
            keepouts.append(k)
    print("temporary keepouts:", len(keepouts))
    # drop any previous auto-routed tracks/vias (keep the explicitly generated ones: width 0.5 mm stubs)
    pcbnew.ExportSpecctraDSN(b, DSN)
    import shutil
    java = shutil.which("java")
    if java is None:
        r0 = subprocess.run(["mise", "which", "java"], cwd=ROOT, text=True, capture_output=True)
        java = r0.stdout.strip() or "java"
    cmd = [java, "-jar", JAR, "--gui.enabled=false", "-de", DSN, "-do", SES, "-mp", str(passes),
           "-mt", "4", "--router.layers.routable=true,false,true,true"]
    print(" ".join(cmd))
    r = subprocess.run(cmd, cwd=os.path.join(ROOT, "out"), text=True, capture_output=True)
    tail = "\n".join(l for l in r.stdout.splitlines() if "nalytics" not in l)[-3000:]
    print(tail)
    if not os.path.exists(SES):
        print("freerouting produced no session file"); print(r.stderr[-2000:])
        sys.exit(1)
    if not pcbnew.ImportSpecctraSES(b, SES):
        print("SES import failed"); sys.exit(1)
    for k in keepouts:
        b.Remove(k)
    for z in hidden:
        b.Add(z)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
    print("routed board saved:", PCB)


if __name__ == "__main__":
    main()
