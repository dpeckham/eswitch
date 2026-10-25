#!/usr/bin/env python3
"""Native KiCad CLI operations; copper filling deliberately avoids Python SWIG."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'out/redesign'


def cli():
    override=os.environ.get('KICAD_CLI')
    mac='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
    return override or (mac if Path(mac).exists() else shutil.which('kicad-cli'))


def run(args,log):
    result=subprocess.run([cli(),*map(str,args)],capture_output=True,text=True)
    log.write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'KiCad exited {result.returncode}; see {log}')
    return result


def drc(board,refill=True,parity=False):
    board=Path(board).resolve()
    stem=board.stem
    report=OUT/f'{stem}-drc.json'
    args=['pcb','drc','--severity-all','--format','json','-o',report]
    if refill: args+=['--refill-zones','--save-board']
    if parity: args+=['--schematic-parity']
    run([*args,board],OUT/f'{stem}-drc.log')
    data=json.loads(report.read_text())
    print(Counter((v['severity'],v['type']) for v in data['violations']))
    print('Unconnected:',len(data['unconnected_items']),'Parity:',len(data.get('schematic_parity',[])))
    return data


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('board',type=Path)
    p.add_argument('--no-refill',action='store_true')
    p.add_argument('--parity',action='store_true')
    a=p.parse_args()
    drc(a.board,not a.no_refill,a.parity)
