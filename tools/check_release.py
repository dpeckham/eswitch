#!/usr/bin/env python3
"""Refuse fabrication output until the engineering review is explicitly closed."""
import json
from pathlib import Path
from verify import source_hashes, sha256


def check_evidence(root):
    path = root / "out/verification/manifest.json"
    if not path.exists():
        raise SystemExit("Run `just verify`: no verification evidence exists")
    evidence = json.loads(path.read_text())
    if evidence.get("passed") is not True or evidence.get("sources") != source_hashes(root):
        raise SystemExit("Run `just verify`: verification failed or design files changed")
    if not evidence.get("reports"):
        raise SystemExit("Verification reports are missing")
    for name, digest in evidence["reports"].items():
        report = root / name
        if not report.is_file() or sha256(report) != digest:
            raise SystemExit(f"Verification report missing or changed: {name}")
    return evidence


def check(root=None):
    root = root or Path(__file__).resolve().parent.parent
    with (root / "docs/release-status.json").open() as f:
        state = json.load(f)
    if state.get("fabrication_approved") is not True or state.get("blockers"):
        raise SystemExit("FABRICATION BLOCKED: see docs/critical-review.md and docs/release-status.json.\n"
                         + "\n".join("- " + issue for issue in state.get("blockers", [])))
    evidence = check_evidence(root)
    if state.get("approved_sources") != evidence["sources"]:
        raise SystemExit("Fabrication approval does not identify these exact verified sources")


if __name__ == "__main__":
    check()
