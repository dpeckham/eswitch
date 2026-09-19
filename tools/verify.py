#!/usr/bin/env python3
"""Verify the saved design and bind the results to its exact source files.

Does not regenerate the schematic, PCB, routing or libraries. A passing CAD
report is evidence for engineering review, never an electrical qualification.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/verification"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(root=ROOT):
    files = [root / name for name in ("eswitch.kicad_pcb", "eswitch.kicad_sch",
             "eswitch.kicad_pro", "fp-lib-table", "sym-lib-table", "justfile",
             "docs/fabrication-stackup-evidence.json")]
    files += sorted((root / "lib").rglob("*.kicad_mod"))
    files += sorted((root / "lib").glob("*.kicad_sym"))
    files += sorted((root / "tools").glob("*.py"))
    files += sorted((root / "docs/evidence").glob("*.json"))
    files += sorted((root / "docs").glob("*-calculations.json"))
    files += sorted((root / "docs").glob("prototype-*.md"))
    files += [root / "docs" / name for name in
              ("power-review.md", "input-clamp-review.md", "input-startup-explained.md",
               "bring-up.md", "assembly.md", "design-constraints.md")
              if (root / "docs" / name).exists()]
    return {str(p.relative_to(root)): sha256(p) for p in files}


def run(name, *command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (OUT / f"{name}.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"{name} failed: see out/verification/{name}.log")
    print(f"PASS {name}", flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
                    passed=False, sources=source_hashes())
    manifest = OUT / "manifest.json"
    # Invalidate previous success before running anything.
    manifest.write_text(json.dumps(evidence, indent=2) + "\n")
    try:
        run("netlist-export", "kicad-cli", "sch", "export", "netlist", "--format",
            "kicadsexpr", "-o", "out/eswitch.net", "eswitch.kicad_sch")
        run("circuit-netlist", sys.executable, "tools/check_netlist.py", "out/eswitch.net")
        run("buck-capacitance", sys.executable, "tools/buck_analysis.py", "--check")
        run("input-stage-calculation", sys.executable, "tools/input_stage_analysis.py", "--check")
        run("input-transient-evidence", sys.executable, "tools/input_stage_transient.py", "--check")
        run("erc", "kicad-cli", "sch", "erc", "--severity-all", "--exit-code-violations",
            "--format", "json", "-o", str(OUT / "erc.json"), "eswitch.kicad_sch")
        for name, script in (("board-netlist", "check_board_netlist.py"),
                             ("fuse-silk", "check_fuse_silk.py"),
                             ("geometry", "check_geometry.py")):
            run(name, "kicad", "python3.11", f"tools/{script}")
        run("drc", "kicad-cli", "pcb", "drc", "--schematic-parity", "--severity-all",
            "--format", "json", "-o", str(OUT / "drc.json"), "eswitch.kicad_pcb")
        report = json.loads((OUT / "drc.json").read_text())
        counts = dict(drc_errors=sum(v["severity"] == "error" for v in report["violations"]),
                      drc_warnings=sum(v["severity"] == "warning" for v in report["violations"]),
                      unconnected=len(report["unconnected_items"]),
                      schematic_parity=len(report["schematic_parity"]))
        evidence["counts"] = counts
        if any(counts.values()) or report.get("exclusions"):
            raise RuntimeError(f"Unresolved CAD findings: {counts}")
        if source_hashes() != evidence["sources"]:
            raise RuntimeError("Design changed during verification; rerun against the final files")
        evidence["passed"] = True
    except (RuntimeError, OSError) as exc:
        evidence["failure"] = str(exc)
    evidence["reports"] = {str(p.relative_to(ROOT)): sha256(p)
                           for p in sorted(OUT.iterdir()) if p != manifest and p.is_file()}
    manifest.write_text(json.dumps(evidence, indent=2) + "\n")
    if not evidence["passed"]:
        raise SystemExit(evidence["failure"])
    print("Saved design verified; evidence: out/verification/manifest.json")


if __name__ == "__main__":
    main()
