#!/usr/bin/env python3
"""Refuse fabrication output until the engineering review is explicitly closed."""
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent.parent
    with (root / "docs/release-status.json").open() as f:
        state = json.load(f)
    if state.get("fabrication_approved") is not True or state.get("blockers"):
        raise SystemExit("FABRICATION BLOCKED: see docs/critical-review.md and docs/release-status.json.\n"
                         + "\n".join("- " + issue for issue in state.get("blockers", [])))


if __name__ == "__main__":
    check()
