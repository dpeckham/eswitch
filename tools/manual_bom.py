#!/usr/bin/env python3
"""Generate a per-board manual-assembly BOM from the circuit and dated stock audit.

No scraping or purchasing. Stock is a dated observation, never a reservation.
Fail for missing parts, insufficient inventory, or an audit older than one day.
"""
import argparse
import csv
from collections import defaultdict
from datetime import date
import json
from pathlib import Path

import design

ROOT = Path(__file__).resolve().parent.parent
EXTRAS = [
    (5, "0287005.PXCN", "Littelfuse", "F3-F7 inserts", "5 A ATO fuse; ambient derating applies"),
    (2, "0287010.PXCN", "Littelfuse", "F1-F2 inserts", "10 A ATO fuse; ambient derating applies"),
    (1, "0287020.PXCN", "Littelfuse", "F8 insert", "20 A ATO fuse; NOT 20 A continuous at all ambients"),
    (12, "R30-1001002", "Harwin", "H1-H12 standoffs", "M3 x 10 mm; verify enclosure clearance"),
]


def rows():
    grouped = defaultdict(list)
    for p in design.build():
        if not p.footprint or p.ref.startswith(("H", "NT", "TP")):
            continue
        if not p.fields.get("MPN") or not p.fields.get("Manufacturer"):
            raise ValueError(f"Missing exact manufacturer/MPN: {p.ref}")
        grouped[p.fields["MPN"]].append(p)
    result = []
    for mpn, parts in grouped.items():
        qty = len(parts) * (3 if mpn == "3557" else 1)
        p = parts[0]
        description = ", ".join(dict.fromkeys(part.value for part in parts)) + " / " + p.footprint
        if mpn == "3557":
            description = "ATO holder clips; quantity counts individual clips, three per channel"
        result.append(dict(mpn=mpn, manufacturer=p.fields["Manufacturer"], per_board=qty,
                           required=qty, references=", ".join(p.ref for p in parts),
                           description=description,
                           assembly="THT" if mpn in ("3557", "74650195", "691218410002", "61300411121") else "SMD"))
    for qty, mpn, manufacturer, references, description in EXTRAS:
        result.append(dict(mpn=mpn, manufacturer=manufacturer, per_board=qty, required=qty,
                           references=references, description=description, assembly="Hardware"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-stale", action="store_true", help="Reproduce the historical BOM; not a current stock check")
    args = parser.parse_args()
    with (ROOT / "docs/digikey-stock.json").open() as f:
        audit = {p["mpn"]: p for p in json.load(f)["parts"]}
    items = rows()
    for item in items:
        p = audit.get(item["mpn"])
        if p is None or p["stock"] is None or p["stock"] < item["required"]:
            raise SystemExit(f"Insufficient/unverified DigiKey stock: {item['mpn']} (need {item['required']})")
        age = (date.today() - date.fromisoformat(p["checked"])).days
        if not args.allow_stale and (age < 0 or age > 1):
            raise SystemExit(f"Refresh DigiKey inventory before ordering: {item['mpn']} checked {p['checked']}")
        item.update(p)
    target = ROOT / "fab/digikey/eswitch-digikey-bom.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["Quantity", "Manufacturer Part Number", "Manufacturer", "Customer Reference", "Description"])
        for p in items:
            writer.writerow([p["required"], p["mpn"], p["manufacturer"], p["references"], p["description"]])
    detail = ROOT / "fab/digikey/stock-audit.csv"
    with detail.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["MPN", "Per board", "Boards", "Required", "DigiKey stock observed", "Checked UTC date", "Product URL", "Assembly"])
        for p in items:
            writer.writerow([p["mpn"], p["per_board"], 1, p["required"], p["stock"], p["checked"], p["url"], p["assembly"]])
    print(f"{len(items)} line items; quantities for ONE board; dated stock covers every required quantity")
    print("Apply your desired build quantity when ordering; no batch multiplier is included.")
    print("No spare allowance included. No parts purchased/reserved. See docs/critical-review.md for PCB release status.")


if __name__ == "__main__":
    main()
