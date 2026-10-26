#!/usr/bin/env python3
"""Export fabrication/placement files from the checked authoritative board."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
import shutil
import os
import subprocess

from native import OUT, drc, run

HERE=Path(__file__).resolve().parent
BOARD=HERE/'eswitch-simple.kicad_pcb'
FAB=HERE.parent/'fab'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    FAB.mkdir(parents=True,exist_ok=True)
    if not BOARD.exists():
        raise SystemExit('Authoritative routed board is not available yet.')
    report=drc(BOARD,parity=True)
    if report['violations'] or report['unconnected_items'] or report.get('schematic_parity'):
        raise SystemExit('Resolve DRC, routing and schematic parity before export.')
    python=os.environ.get('KICAD_PYTHON','/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9')
    geometry=subprocess.run([python,str(HERE/'power_geometry.py'),str(BOARD),'--check',
                             '--output',str(HERE/'power-copper-review.json')],capture_output=True,text=True)
    (OUT/'export-power-geometry.log').write_text(geometry.stdout+geometry.stderr)
    if geometry.returncode:raise RuntimeError('Power geometry regression failed; see out/redesign/export-power-geometry.log')
    feature_screen=OUT/'jlc-feature-screen.json'
    result=subprocess.run([python,str(HERE/'jlc_feature_screen.py'),str(BOARD),
                           '--output',str(feature_screen)],capture_output=True,text=True)
    (OUT/'export-jlc-feature-screen.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('JLCPCB selected-feature screen failed; see out/redesign/export-jlc-feature-screen.log')
    # Native refilling can change serialized fill ordering. The new PCB has just
    # passed DRC/parity and geometry again; retain the earlier ERC/topology result
    # only if every other verified source is byte-for-byte unchanged.
    verification_path=OUT/'verification.json'
    if verification_path.exists():
        verification=json.loads(verification_path.read_text())
        refreshed={str(p.relative_to(HERE.parent)):p for p in (BOARD,HERE/'power-copper-review.json')}
        for name,digest in verification['source_sha256'].items():
            if name not in refreshed and hashlib.sha256((HERE.parent/name).read_bytes()).hexdigest()!=digest:
                raise RuntimeError(f'Verified source changed: {name}; run just verify before packaging')
        for name,path in refreshed.items():
            verification['source_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
        verification_path.write_text(json.dumps(verification,indent=2)+'\n')
    result=subprocess.run([python,str(HERE/'assembly.py')],capture_output=True,text=True)
    (OUT/'export-assembly.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Assembly plotting copy failed; see out/redesign/export-assembly.log')
    # Stage a complete new set, avoiding stale files from previous exports.
    with tempfile.TemporaryDirectory(prefix='fabrication-',dir=OUT) as temp:
        stage=Path(temp)
        gerbers=stage/'gerbers'
        gerbers.mkdir()
        run(['pcb','export','gerbers','--layers',
             'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,B.Paste,Edge.Cuts',
             '--output',str(gerbers)+'/',BOARD],OUT/'export-gerbers.log')
        run(['pcb','export','drill','--excellon-separate-th','--generate-map',
             '--map-format','svg','--output',str(gerbers)+'/',BOARD],OUT/'export-drill.log')
        run(['pcb','export','pos','--format','csv','--units','mm','--side','both',
             '--exclude-dnp','--output',stage/'placement.csv',BOARD],OUT/'export-placement.log')
        for name,layers,extra in (
            ('assembly-top','F.Fab,F.SilkS,Edge.Cuts',[]),
            ('assembly-bottom','B.Fab,B.SilkS,Edge.Cuts',['--mirror']),
            ('dimensions','Dwgs.User,Edge.Cuts',[])):
            drawing=BOARD if name=='dimensions' else OUT/'assembly-only.kicad_pcb'
            page=['--page-size-mode','1'] if name=='dimensions' else ['--fit-page-to-board']
            run(['pcb','export','svg','--layers',layers,'--mode-single',*page,'--black-and-white',
                 '--exclude-drawing-sheet',*extra,
                 '--output',stage/f'{name}.svg',drawing],OUT/f'export-{name}.log')
        for name in ('bom-draft.csv','BUILD.md','JLCPCB-ORDER.txt','jlc-stackup-evidence.json',
                     'installation-screen.json','requirements.json',
                     'electrical-screen.json','power-copper-review.json'):
            shutil.copyfile(HERE/name,stage/name)
        shutil.copyfile(feature_screen,stage/'jlc-feature-screen.json')
        shutil.copyfile(verification_path,stage/'verification.json')
        shutil.copyfile(OUT/'eswitch-simple-drc.json',stage/'layout-check.json')
        manifest={str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in stage.rglob('*') if p.is_file()}
        (stage/'manifest.json').write_text(json.dumps(dict(
            board_sha256=hashlib.sha256(BOARD.read_bytes()).hexdigest(),
            status='Released for prototype fabrication and controlled bench testing; not battery-fault, transient or thermal/current qualification',
            files=manifest),indent=2)+'\n')
        destination=FAB/'eswitch-simple-fabrication.zip'
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(stage.rglob('*')):
                if p.is_file(): archive.write(p,p.relative_to(stage))
        print(destination)
        destination=FAB/'eswitch-simple-jlcpcb-gerbers.zip'
        jobs=list(gerbers.glob('*.gbrjob'))
        assert len(jobs)==1, 'Expected one Gerber job'
        attributes=json.loads(jobs[0].read_text())['FilesAttributes']
        assert len(attributes)==11 and sum(a['FileFunction'].startswith('Copper,') for a in attributes)==4
        upload_files=[gerbers/a['Path'] for a in attributes]+[jobs[0],*sorted(gerbers.glob('*.drl'))]
        assert len(upload_files)==14 and all(p.is_file() for p in upload_files), 'Incomplete CAM upload'
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
            for p in upload_files:
                archive.write(p,p.name)
            archive.write(HERE/'JLCPCB-ORDER.txt','JLCPCB-ORDER.txt')
        print(destination)
    destination=FAB/'eswitch-simple-project.zip'
    files=[*HERE.glob('eswitch-simple.kicad_*'),HERE/'fp-lib-table',HERE/'sym-lib-table',
           *[HERE/name for name in ('README.md','BUILD.md','bom-draft.csv','pin-map.json',
                                    'requirements.json','electrical-screen.json','cost-estimate.json','power-copper-review.json',
                                    'JLCPCB-ORDER.txt','jlc-stackup-evidence.json','installation-screen.json')],
           *[p for p in (HERE/'lib').rglob('*') if p.is_file()]]
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            if p.suffix not in ('.kicad_pcb','.kicad_pro','.kicad_sch') and p.name.startswith('eswitch-simple.kicad_'):continue
            archive.write(p,Path('eswitch-simple')/p.relative_to(HERE))
    print(destination)
    # Plotting copies must not appear as extra editable KiCad projects.
    for suffix in ('.kicad_pcb','.kicad_pro','.kicad_prl'):
        (OUT/('assembly-only'+suffix)).unlink(missing_ok=True)


if __name__=='__main__': main()
