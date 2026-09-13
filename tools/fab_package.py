#!/usr/bin/env python3
"""Build upload packages for PCBWay and JLCPCB into fab/.

Outputs:
  fab/eswitch-gerbers.zip          gerbers + Excellon drill + stackup note (both vendors)
  fab/jlcpcb/eswitch-bom.csv       Comment, Designator, Footprint, LCSC Part #
  fab/jlcpcb/eswitch-cpl.csv       Designator, Mid X, Mid Y, Layer, Rotation
  fab/pcbway/eswitch-bom.csv       PCBWay assembly BOM template columns
  fab/pcbway/eswitch-cpl.csv       Designator, Footprint, Mid X, Mid Y, Layer, Rotation
"""
import csv
import glob
import os
import re
import shutil
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "fab")
FAB = os.path.join(ROOT, "fab")
PCB = os.path.join(ROOT, "eswitch.kicad_pcb")
SCH = os.path.join(ROOT, "eswitch.kicad_sch")

# LCSC part numbers for JLCPCB assembly. Only entries I am confident about; everything else
# is left for JLCPCB's parts-matching step (it auto-suggests by value + package).
LCSC = {
    ("ESP32-S3-WROOM-1-N8", "ESP32-S3-WROOM-1"): "C2913202",
    ("USBLC6-2SC6", "SOT-23-6"): "C7519",
    ("BAT54S", "SOT-23"): "C47547",
    ("4.7k", "0603"): "C23162",
    ("10k", "0603"): "C25804",
    ("1k", "0603"): "C21190",
    ("5.1k", "0603"): "C23186",
    ("2.2k", "0603"): "C4190",
    ("47k", "0603"): "C25819",
    ("1.2k 1%", "0603"): "C22765",
    ("3.9k", "0603"): "C23018",
    ("200k 1%", "0603"): "C25811",
    ("100nF 50V", "0603"): "C14663",
    ("100nF 25V", "0603"): "C14663",
    ("100nF", "0603"): "C14663",
    ("1uF", "0603"): "C15849",
    ("220pF 50V", "0603"): "C1653",
    ("100nF 50V", "0805"): "C49678",
    ("10uF 10V", "0805"): "C15850",
    ("GREEN", "LED_0603"): "C72043",
    ("BLUE", "LED_0603"): "C72041",
}

# Off-board items to order with the parts (not in the schematic)
EXTRAS = [
    (8, "0287015.PXCN", "Littelfuse", "F1-F8 fuse", "ATO blade fuse 15 A (size per load; 15 A max)"),
    (2, "0287003.PXCN", "Littelfuse", "spare", "ATO blade fuse 3 A spare"),
    (4, "R30-1001002", "Harwin", "H1-H4", "M3 x 10 mm hex standoff (or any M3 standoff)"),
]

STACKUP_NOTE = """eswitch rev A - fabrication notes
==================================
Layers:            4 (F.Cu, In1.Cu=GND plane, In2.Cu=PWR, B.Cu)
Board size:        181.0 x 57.5 mm
Thickness:         1.6 mm
Copper weight:     2 oz outer, 1 oz inner (high-current bus and load strips on the outer layers)
Material:          FR-4 TG150 or better
Surface finish:    ENIG preferred (HASL acceptable)
Solder mask:       green; silkscreen white
Min track/space:   0.15 / 0.20 mm
Min via:           0.5 mm pad / 0.3 mm drill (module thermal vias 0.2 mm drill)
Drill file:        Excellon, PTH and NPTH merged (eswitch.drl), plus .drl map
Gerber layer map:  eswitch-F_Cu / eswitch-GND (In1) / eswitch-PWR (In2) / eswitch-B_Cu,
                   F/B_Mask, F/B_Paste, F/B_Silkscreen, Edge_Cuts, eswitch-job.gbrjob
Assembly:          all SMD parts on the BOTTOM side; through-hole parts on the top are
                   hand-soldered (fuse clips, terminal block, screw terminals, header).
"""


def run(*args):
    cmd = ["kicad-cli"] + list(args)
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"{' '.join(cmd)}\n{r.stdout}\n{r.stderr}")


def pkg_name(fp):
    """Short package name for vendor BOMs from a KiCad footprint id."""
    name = fp.split(":")[-1]
    m = re.match(r"^[RCL]_(\d{4})_\d+Metric", name)
    if m:
        return m.group(1)
    m = re.match(r"^LED_(\d{4})_\d+Metric", name)
    if m:
        return "LED_" + m.group(1)
    m = re.match(r"^Fuse_(\d{4})_\d+Metric", name)
    if m:
        return m.group(1)
    for k in ("SOT-23-6", "SOT-23", "D_SMA", "D_SMB"):
        if name.startswith(k):
            return k.replace("D_", "")
    return name


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in glob.glob(os.path.join(OUT, "*")):
        if os.path.isfile(f):
            os.remove(f)
    run("pcb", "export", "gerbers", "-o", OUT + "/", "--board-plot-params", PCB)
    run("pcb", "export", "drill", "-o", OUT + "/", "--generate-map", "--map-format", "gerberx2", PCB)
    run("pcb", "export", "pos", "-o", os.path.join(OUT, "eswitch-pos.csv"), "--format", "csv", "--units", "mm",
        "--use-drill-file-origin", PCB)
    run("pcb", "export", "pos", "-o", os.path.join(OUT, "eswitch-pos-smd.csv"), "--format", "csv", "--units", "mm",
        "--use-drill-file-origin", "--smd-only", PCB)
    run("sch", "export", "bom", "-o", os.path.join(OUT, "eswitch-bom.csv"),
        "--fields", "Reference,Value,Footprint,Manufacturer,MPN,Note,${QUANTITY}", "--group-by", "Value,Footprint,MPN", SCH)
    with open(os.path.join(OUT, "README-fab.txt"), "w") as f:
        f.write(STACKUP_NOTE)

    for d in (FAB, os.path.join(FAB, "jlcpcb"), os.path.join(FAB, "pcbway")):
        os.makedirs(d, exist_ok=True)
    zpath = os.path.join(FAB, "eswitch-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(OUT, "*"))):
            if f.endswith((".gbr", ".gbrjob", ".drl", ".txt")) or "-drl" in f:
                z.write(f, os.path.basename(f))
    print("wrote", zpath)

    # ---- BOM rows (per line item) and per-designator placement
    bom = list(csv.DictReader(open(os.path.join(OUT, "eswitch-bom.csv"))))
    pos = {r["Ref"]: r for r in csv.DictReader(open(os.path.join(OUT, "eswitch-pos.csv")))}
    smd = {r["Ref"]: r for r in csv.DictReader(open(os.path.join(OUT, "eswitch-pos-smd.csv")))}
    smd_refs = set(smd)

    def expand(refs):
        out = []
        for part in refs.split(","):
            part = part.strip()
            m = re.match(r"^([A-Za-z#]+)(\d+)-([A-Za-z#]+)?(\d+)$", part)
            if m and (m.group(3) is None or m.group(3) == m.group(1)):
                out += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(4)) + 1)]
            else:
                out.append(part)
        return out

    # JLCPCB
    with open(os.path.join(FAB, "jlcpcb", "eswitch-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for r in bom:
            refs = [x for x in expand(r["Reference"]) if x in smd_refs]
            if not refs:
                continue
            pkg = pkg_name(r["Footprint"])
            lcsc = LCSC.get((r["Value"], pkg), "")
            comment = r["MPN"] or r["Value"]
            w.writerow([comment, ",".join(refs), pkg, lcsc])
    with open(os.path.join(FAB, "jlcpcb", "eswitch-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref, r in sorted(smd.items()):
            w.writerow([ref, f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm",
                        "Top" if r["Side"] == "top" else "Bottom", f"{float(r['Rot']):.1f}"])
    # PCBWay
    with open(os.path.join(FAB, "pcbway", "eswitch-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Item #", "Designator", "Qty", "Manufacturer", "Mfg Part #", "Description / Value",
                    "Package/Footprint", "Type", "Your Instructions / Notes"])
        for i, r in enumerate(bom, 1):
            refs = expand(r["Reference"])
            typ = "SMD" if refs[0] in smd_refs else "Through-hole"
            w.writerow([i, ",".join(refs), len(refs), r["Manufacturer"], r["MPN"], r["Value"],
                        pkg_name(r["Footprint"]), typ, r["Note"]])
    with open(os.path.join(FAB, "pcbway", "eswitch-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Footprint", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref, r in sorted(pos.items()):
            w.writerow([ref, r["Package"], f"{float(r['PosX']):.3f}", f"{float(r['PosY']):.3f}",
                        "Top" if r["Side"] == "top" else "Bottom", f"{float(r['Rot']):.1f}"])
    # DigiKey myLists upload: Quantity, Manufacturer Part Number, Customer Reference, Description
    os.makedirs(os.path.join(FAB, "digikey"), exist_ok=True)
    with open(os.path.join(FAB, "digikey", "eswitch-digikey-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Quantity", "Manufacturer Part Number", "Manufacturer", "Customer Reference", "Description"])
        for r in bom:
            if r["Reference"].startswith("H"):
                continue
            qty = int(r["QUANTITY"])
            if r["MPN"] == "3557":
                qty *= 3
            w.writerow([qty, r["MPN"], r["Manufacturer"], r["Reference"],
                        f"{r['Value']} {pkg_name(r['Footprint'])} {r['Note']}".strip()])
        for qty, mpn, mfr, ref, desc in EXTRAS:
            w.writerow([qty, mpn, mfr, ref, desc])
    shutil.copy(os.path.join(OUT, "README-fab.txt"), os.path.join(FAB, "README-fab.txt"))
    print("wrote", FAB)


if __name__ == "__main__":
    main()
