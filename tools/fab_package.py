#!/usr/bin/env python3
"""Package released bare-board fabrication files and the exact-MPN manual BOM.

No value/package-only assembly substitutions. Fabrication remains gated until
the findings in docs/critical-review.md are closed; use `just package` so ERC and
DRC run too. Existing legacy packages are intentionally not overwritten.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from check_release import check

ROOT = Path(__file__).resolve().parent.parent
FAB = ROOT / "fab"

STACKUP_NOTE = """eswitch rev A - fabrication notes
Layers: 4 (F.Cu, In1.Cu=GND, In2.Cu=PWR, B.Cu)
Board: 181.0 x 57.5 mm, 1.6 mm nominal thickness
Service: OSH Park standard four-layer, ENIG, purple solder mask, white silkscreen
Copper: 1 / 0.5 / 0.5 / 1 oz; NOT 1 oz on every layer
Design constraints: 0.15 mm track, 0.20 mm clearance,
                    0.254 mm finished drill, 0.4 mm copper-to-edge
Assembly: three boards, manual paste/hot-air or hot-plate SMD assembly;
          most SMD bottom, SW1/SW2 top; THT installed after reflow.
Purchasing: exact manufacturer/MPN DigiKey BOM, three-board minimum quantities.
Fuse silk: circuit number and MAX FUSE rating, not continuous-current qualification.
Read docs/assembly.md and the release record before assembly.
"""


def run(*args):
    subprocess.run(["kicad-cli", *map(str, args)], cwd=ROOT, check=True)


def main():
    check()
    # Validate dated availability first; never overwrite this with a per-board
    # vendor BOM or an unchecked value/package cross-reference.
    subprocess.run([sys.executable, str(ROOT / "tools/manual_bom.py")], check=True)
    FAB.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eswitch-fab-") as temporary:
        target = Path(temporary)
        pcb = ROOT / "eswitch.kicad_pcb"
        run("pcb", "export", "gerbers", "-o", str(target) + "/", "--board-plot-params", pcb)
        run("pcb", "export", "drill", "-o", str(target) + "/", "--generate-map",
            "--map-format", "gerberx2", pcb)
        (target / "README-fab.txt").write_text(STACKUP_NOTE)
        with zipfile.ZipFile(FAB / "eswitch-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(target.iterdir()):
                if path.is_file():
                    archive.write(path, path.name)
    print("Wrote released bare-board package and three-board DigiKey BOM")


if __name__ == "__main__":
    main()
