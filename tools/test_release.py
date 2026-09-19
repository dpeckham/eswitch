"""Regression checks for stale evidence and accidental fabrication release."""
import json
from pathlib import Path
import tempfile
import unittest

from check_release import check, check_evidence
from verify import sha256, source_hashes


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("eswitch.kicad_pcb", "eswitch.kicad_sch", "eswitch.kicad_pro",
                     "fp-lib-table", "sym-lib-table", "justfile",
                     "docs/fabrication-stackup-evidence.json", "tools/verify.py",
                     "docs/prototype-release.md", "docs/power-review.md",
                     "lib/example.kicad_sym", "lib/eswitch.pretty/example.kicad_mod",
                     "out/verification/drc.json"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n")
        self.sources = source_hashes(self.root)
        self.manifest = self.root / "out/verification/manifest.json"
        self.evidence = dict(passed=True, sources=self.sources,
                            reports={"out/verification/drc.json": sha256(self.root / "out/verification/drc.json")})
        self.manifest.write_text(json.dumps(self.evidence))
        self.state = dict(fabrication_approved=True, blockers=[], approved_sources=self.sources)
        self.write_state()

    def write_state(self):
        (self.root / "docs/release-status.json").write_text(json.dumps(self.state))

    def test_matching_verified_approved_sources_pass(self):
        check(self.root)

    def test_flag_alone_cannot_release_a_design(self):
        self.state.pop("approved_sources")
        self.write_state()
        with self.assertRaisesRegex(SystemExit, "exact verified"):
            check(self.root)

    def test_open_engineering_blocker_prevents_release(self):
        self.state["blockers"] = ["Startup SOA unverified"]
        self.write_state()
        with self.assertRaisesRegex(SystemExit, "FABRICATION BLOCKED"):
            check(self.root)

    def test_changed_board_or_footprint_invalidates_evidence(self):
        for name in ("eswitch.kicad_pcb", "lib/eswitch.pretty/example.kicad_mod",
                     "docs/prototype-release.md", "docs/power-review.md"):
            with self.subTest(name=name):
                path = self.root / name
                before = path.read_bytes()
                path.write_text("changed\n")
                with self.assertRaisesRegex(SystemExit, "files changed"):
                    check_evidence(self.root)
                path.write_bytes(before)

    def test_missing_or_modified_report_invalidates_evidence(self):
        path = self.root / "out/verification/drc.json"
        path.write_text("changed\n")
        with self.assertRaisesRegex(SystemExit, "report missing or changed"):
            check_evidence(self.root)
        path.unlink()
        with self.assertRaisesRegex(SystemExit, "report missing or changed"):
            check_evidence(self.root)

    def test_failed_verification_cannot_be_reused(self):
        self.evidence["passed"] = False
        self.manifest.write_text(json.dumps(self.evidence))
        with self.assertRaisesRegex(SystemExit, "verification failed"):
            check_evidence(self.root)

    def test_no_verification_cannot_be_released(self):
        self.manifest.unlink()
        with self.assertRaisesRegex(SystemExit, "no verification"):
            check(self.root)


if __name__ == "__main__":
    unittest.main()
