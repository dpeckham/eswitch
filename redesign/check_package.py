#!/usr/bin/env python3
"""Independently verify delivered archives, BOM upload and saved source hashes."""
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sha=lambda data:hashlib.sha256(data).hexdigest()


def main():
    fab=ROOT/'fab';design=ROOT/'redesign'
    with zipfile.ZipFile(fab/'eswitch-simple-fabrication.zip') as full, \
         zipfile.ZipFile(fab/'eswitch-simple-jlcpcb-gerbers.zip') as upload, \
         zipfile.ZipFile(fab/'eswitch-simple-project.zip') as project:
        manifest=json.loads(full.read('manifest.json'))
        assert manifest['board_sha256']==sha((design/'eswitch-simple.kicad_pcb').read_bytes())
        assert set(full.namelist())==set(manifest['files'])|{'manifest.json'}
        for name,digest in manifest['files'].items():assert sha(full.read(name))==digest,name
        for name in upload.namelist():
            source=name if name=='JLCPCB-ORDER.txt' else 'gerbers/'+name
            assert upload.read(name)==full.read(source),name
        for name in project.namelist():
            source=design/Path(name).relative_to('eswitch-simple')
            assert project.read(name)==source.read_bytes(),name
        verification=json.loads(full.read('verification.json'))
        for name,digest in verification['source_sha256'].items():
            assert sha((ROOT/name).read_bytes())==digest,name
        for key in ('erc_violations','pcb_drc_violations','pcb_unconnected','pcb_schematic_parity'):
            assert verification[key]==0,key
        for report in ('power-copper-review.json','power-transition-review.json'):
            assert json.loads(full.read(report))['board_sha256']==manifest['board_sha256'],report
        readcsv=lambda data:list(csv.DictReader(io.StringIO(data.decode())))
        bom=readcsv(full.read('bom-draft.csv'));order=readcsv(full.read('eswitch-digikey-qty1.csv'))
        assert {r['MPN']:int(r['Quantity per board']) for r in bom}=={
            r['Manufacturer Part Number']:int(r['Quantity']) for r in order}
        assert full.read('eswitch-digikey-qty1.csv')==(fab/'eswitch-digikey-qty1.csv').read_bytes()
        print(f'Archives/source hashes match; zero ERC/DRC/parity/gaps; BOM {len(order)} lines / {sum(int(r["Quantity"]) for r in order)} pieces per board.')


if __name__=='__main__':main()
