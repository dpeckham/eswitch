#!/usr/bin/env python3
"""Package checked revision-B CAM files, or an explicitly unreleased review ZIP."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from check_release import check, check_evidence
from verify import source_hashes, sha256

ROOT = Path(__file__).resolve().parent.parent
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts'
STACKUP_NOTE = '''eswitch revision B - bare-board fabrication specification
Board: 253.0 x 75.0 mm; 4 layers; 1.6 mm nominal (selected stackup 1.59 mm).
Manufacturer/stackup: JLCPCB JLC041622-3313; ENIG; 2 oz outer AND inner.
Layer order: F.Cu / In1.Cu (GND) / In2.Cu (power and GND) / B.Cu.
Finished copper used by impedance model: 70 / 61 / 61 / 70 micrometres.
Dielectrics: 0.1835 / 0.9600 / 0.1835 mm. See stackup evidence JSON.
USB: L4 referenced to L3, nominal 90 ohm differential;
     0.235 mm width / 0.215 mm straight-pair gap.
Do not substitute copper weights or stackup without recalculating USB geometry.
CAD rules: 0.18 mm track, 0.20 mm clearance, 0.30 mm finished through-drill,
           0.40 mm copper-to-edge, 0.10 mm minimum via annular ring.
Build quantity: three manual assemblies; BOM quantities include all three.
Select the fabricator's offered bare-board batch quantity covering at least three.
PTH and NPTH drills are separate; preserve plating classification.
Paste layers are included for stencil preparation; this is not a PCBA order.
The 253 x 75 mm outline is measured on its centreline (KiCad's job reports
253.1 x 75.1 mm including the outline stroke).
Outputs overhang board edge; ESP32 antenna overhang is deliberate.
No automatic part substitutions. Fuse limits are not continuous-current ratings.
Read assembly notes, engineering status and bring-up plan before assembly.
'''


def run(*args):
    subprocess.run(['kicad-cli', *map(str, args)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', action='store_true',
                        help='Unreleased CAM review only; never creates a fabrication release')
    args = parser.parse_args()
    evidence = check_evidence(ROOT)
    if not args.review:
        check()
    bom_command = [sys.executable, str(ROOT / 'tools/manual_bom.py')]
    if args.review:
        bom_command.append('--allow-stale')
    subprocess.run(bom_command, check=True, cwd=ROOT)
    destination = ROOT / ('out/review' if args.review else 'fab/revision-b')
    destination.mkdir(parents=True, exist_ok=True)
    status = 'NOT FOR FABRICATION - ENGINEERING REVIEW OPEN' if args.review else 'RELEASED FOR PROTOTYPE FABRICATION'
    name = 'eswitch-revB-NOT-FOR-FABRICATION.zip' if args.review else 'eswitch-revB-gerbers.zip'
    with tempfile.TemporaryDirectory(prefix='eswitch-package-') as temporary:
        target = Path(temporary)
        cam = target / 'gerbers'
        cam.mkdir()
        pcb = ROOT / 'eswitch.kicad_pcb'
        run('pcb', 'export', 'gerbers', '-o', str(cam) + '/', '--layers', LAYERS, pcb)
        run('pcb', 'export', 'drill', '-o', str(cam) + '/', '--generate-map',
            '--excellon-separate-th', '--map-format', 'gerberx2', pcb)
        jobs = list(cam.glob('*.gbrjob'))
        assert len(jobs) == 1, 'Missing Gerber job'
        assert (cam / 'eswitch-PTH.drl').is_file() and (cam / 'eswitch-NPTH.drl').is_file(), 'Missing plated/non-plated drills'
        job = json.loads(jobs[0].read_text())
        assert len([f for f in job['FilesAttributes'] if 'Copper' in f['FileFunction']]) == 4
        (cam / 'README-fab.txt').write_text(status + '\n\n' + STACKUP_NOTE)
        (target / 'README.txt').write_text(status + '\n\n' + STACKUP_NOTE +
            '\nBOM availability is a dated observation; refresh before procurement.\n')
        shutil.copytree(ROOT / 'fab/digikey', target / 'bom')
        shutil.copytree(ROOT / 'out/verification', target / 'verification')
        shutil.copytree(ROOT / 'docs/evidence', target / 'evidence')
        for document in ('release-status.json', 'assembly.md', 'bring-up.md',
                         'fabrication-stackup-evidence.json', 'input-stage-calculations.json',
                         'buck-capacitance-calculations.json', 'power-review.md',
                         'input-startup-explained.md',
                         'input-transient-calculations.json', 'prototype-release.md',
                         'input-clamp-review.md',
                         'input-protection-review.md', 'design-constraints.md'):
            shutil.copy2(ROOT / 'docs' / document, target / document)
        run('sch', 'export', 'pdf', '-o', target / 'eswitch-schematic.pdf', 'eswitch.kicad_sch')
        for side in ('F', 'B'):
            run('pcb', 'export', 'pdf', '--layers', f'{side}.Fab,{side}.Silkscreen,Edge.Cuts',
                '--mode-single', '--black-and-white', '--sketch-pads-on-fab-layers',
                '--exclude-value', *(['--mirror'] if side == 'B' else []),
                '--scale', '1', '-o', target / f'assembly-{side}-1to1.pdf', pcb)
        if source_hashes() != evidence['sources']:
            raise SystemExit('Design changed during packaging; rerun verification')
        files = {str(p.relative_to(target)): sha256(p) for p in sorted(target.rglob('*')) if p.is_file()}
        (target / 'package-manifest.json').write_text(json.dumps(dict(
            status=status, sources=evidence['sources'], files=files), indent=2) + '\n')
        temporary_zip = destination / (name + '.tmp')
        try:
            with zipfile.ZipFile(temporary_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(target.rglob('*')):
                    if path.is_file():
                        archive.write(path, str(path.relative_to(target)))
            os.replace(temporary_zip, destination / name)
        finally:
            temporary_zip.unlink(missing_ok=True)
        inspect_dir = destination / 'gerbers'
        # Replace generated inspection outputs so an old mixed-plating drill or
        # deleted layer cannot survive beside the new package's files.
        if inspect_dir.exists():
            shutil.rmtree(inspect_dir)
        shutil.copytree(cam, inspect_dir)
    print(f'{status}: {destination / name}')


if __name__ == '__main__':
    main()
