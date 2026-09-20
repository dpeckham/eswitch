#!/usr/bin/env python3
"""Independently parse CAM, check plating/dimensions and render review images.

Run with the Gerbonara/CairoSVG environment installed under out/cam-python.
This does not replace native DRC or the fabricator's upload/DFM review.
"""
import argparse
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import zipfile
from gerbonara import LayerStack
from gerbonara.excellon import ExcellonFile
from gerbonara.utils import MM
import cairosvg

ROOT=Path(__file__).resolve().parent.parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'out/revision-c-cam-review')
    args=parser.parse_args();folder=args.directory.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    stack=LayerStack.open(folder)
    copper=list(stack.copper_layers)
    assert len(copper)==4,'CAM must contain four copper layers'
    assert stack.drill_pth and stack.drill_npth
    # This Gerbonara version identifies the separate files by name but does not
    # interpret KiCad 10's X2 plating comments. Verify those explicit declarations
    # before supplying the known plating class to its independent drill parser.
    for name,plated,attribute in [('PTH',True,'Plated,1,4,PTH'),('NPTH',False,'NonPlated,1,4,NPTH')]:
        path=folder/f'eswitch-{name}.drl'
        assert f'TF.FileFunction,{attribute}' in path.read_text(),f'Missing plating declaration: {name}'
        # Its documented plated= argument is also ignored by from_string in
        # this version. Translate only the verified metadata to its supported
        # comment dialect in memory; coordinates/tools and upload bytes stay intact.
        text=path.read_text()
        adapted=text.replace('M48\n','M48\n;TYPE='+('PLATED' if plated else 'NON_PLATED')+'\n',1)
        assert adapted!=text
        parsed=ExcellonFile.from_string(adapted,filename=path)
        setattr(stack,'drill_pth' if plated else 'drill_npth',parsed)
    assert stack.drill_pth.is_plated and stack.drill_npth.is_nonplated
    assert len(stack.drill_npth.objects)==14,'Twelve M3 holes plus two USB locating holes expected'
    bounds=stack.board_bounds(unit=MM)
    width,height=bounds[1][0]-bounds[0][0],bounds[1][1]-bounds[0][1]
    assert abs(width-334)<.2 and abs(height-172)<.2,(width,height)
    for (side,use),layer in stack.graphic_layers.items():
        if use not in ('copper','silk','mask'):continue
        colors={f'{side} {use}':'#143454','mechanical outline':'#808080','drill pth':'#ffffff','drill npth':'#ffffff'}
        svg=str(stack.to_svg(colors=colors,force_bounds=bounds))
        name=f'{side}-{use}'
        (out/(name+'.svg')).write_text(svg)
        cairosvg.svg2png(bytestring=svg.encode(),write_to=str(out/(name+'.png')),output_width=2400,background_color='white')
    hashes={p.name:sha(p) for p in sorted(folder.iterdir()) if p.is_file()}
    archive=folder.parent/'eswitch-revC-gerbers.zip'
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                assert name in hashes and hashlib.sha256(z.read(name)).hexdigest()==hashes[name],name
            job=json.loads(next(folder.glob('*.gbrjob')).read_text())
            required={Path(x['Path']).name for x in job['FilesAttributes']}|{'eswitch-PTH.drl','eswitch-NPTH.drl'}
            assert required.issubset(z.namelist())
    result=dict(checked_utc=datetime.now(timezone.utc).isoformat(),independent_parser='Gerbonara',
        copper_layers=[list(name) for name,layer in copper],outline_extent_mm=[width,height],
        plated_drill_objects=len(stack.drill_pth.objects),nonplated_drill_objects=len(stack.drill_npth.objects),
        separate_plating_verified=True,files=hashes,
        plating_metadata_adapter='Verified KiCad X2 FileFunction translated to Gerbonara TYPE comment in memory only',
        upload_zip_sha256=sha(archive) if archive.exists() else None,
        limitation='Independent CAM parsing/rendering; visual inspection and fabricator upload/DFM review are separate')
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))


if __name__=='__main__':main()
