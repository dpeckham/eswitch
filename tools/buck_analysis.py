#!/usr/bin/env python3
"""Check the selected output-capacitor bank against saved manufacturer models.

Model curves are typical. The extra 20% reserve is an engineering allowance,
not a manufacturer-guaranteed bound or a substitute for prototype validation.
"""
import argparse
import hashlib
import json
from pathlib import Path

import design

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "docs/evidence/buck-capacitance-murata.json"
RESULT = ROOT / "docs/buck-capacitance-calculations.json"
REFERENCES = ("C7", "C8", "C12", "C13")


def analyze():
    parts = {p.ref: p for p in design.build()}
    model = json.loads(MODEL.read_text())
    assert model["mpn"] == "GCM32ER70J476KE19L"
    assert model["model_part"] + "L" == model["mpn"]
    assert parts["U9"].fields["MPN"] == "TPSM63603V3RDHR"
    assert parts["R1"].value == "16.5k 1%", "Recheck capacitance at changed frequency"
    for ref in REFERENCES:
        part = parts[ref]
        assert part.fields["MPN"] == model["mpn"], f"Stale model for {ref}"
        assert part.value == "47uF 6.3V X7R" and part.footprint == design.C1210
        assert part.pins == {"1": "+3V3", "2": "GND"}
    assert {c["temperature_c"] for c in model["curves"]} == set(range(-55, 126, 5))
    samples = []
    for curve in model["curves"]:
        assert curve["ac_vrms"] == 0.01
        points = curve["points_v_uf"]
        assert points[0][0] == 0 and points[-1][0] >= 3.7
        assert all(0 < b[0]-a[0] < 0.04 for a, b in zip(points, points[1:]))
        samples.extend((cap, curve["temperature_c"], volts)
                       for volts, cap in points if volts <= 3.7)
    cap, temperature, volts = min(samples)
    guarded_bank = len(REFERENCES) * cap * 0.90 * 0.80
    assert guarded_bank > 40, "Insufficient effective capacitance design margin"
    return {
        "status": "model_screen_pass_prototype_validation_required",
        "design_sha256": hashlib.sha256((ROOT / "tools/design.py").read_bytes()).hexdigest(),
        "evidence_sha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
        "mpn": model["mpn"], "references": list(REFERENCES),
        "nominal_bank_uf": 188, "required_effective_uf": 40,
        "minimum_sampled_single_cap_uf": cap,
        "minimum_sample_location": {"temperature_c": temperature, "dc_v": volts},
        "initial_tolerance_factor": 0.90, "additional_engineering_reserve_factor": 0.80,
        "guarded_bank_uf": guarded_bank,
        "margin_above_requirement_percent": (guarded_bank/40-1)*100,
        "limits": [
            "Exact-part typical curves sampled every 5 C from -55 to 125 C and under 0.04 V from 0 to 3.7 V; not a continuous guaranteed bound",
            "Curves combine temperature, DC bias and 10 mVrms AC amplitude; do not apply temperature derating a second time",
            "Additional 20% engineering reserve covers unmodelled variation/ageing; it is not a manufacturer specification",
            "6.3 V parts are on the 3.3 V rail only; never substitute them on VIN or battery nets",
            "Larger bank changes regulator startup charge and USB inrush; bench startup, stability and current-budget tests remain required"
        ],
        "sources": [model["viewer_url"], "https://www.ti.com/lit/ds/symlink/tpsm63603.pdf"]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Reject stale saved calculations")
    args = parser.parse_args()
    result = analyze()
    if args.check:
        assert json.loads(RESULT.read_text()) == result, "Regenerate buck capacitance calculations"
    else:
        RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Buck capacitor model screen: {result['guarded_bank_uf']:.2f} uF with reserve; "
          "40 uF required. Prototype validation remains open.")


if __name__ == "__main__":
    main()
