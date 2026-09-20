#!/usr/bin/env python3
"""Reconcile revision-C metadata, 2oz PTH lands and readable assembly silk.

Does not reroute copper or suppress DRC findings.
"""
from pathlib import Path
import pcbnew
from gen_pcb import V,NETLIST,apply_rules,persist_project_rules
from pcb_nets import sync_metadata
from pcb_io import save_board,fill_zones

ROOT=Path(__file__).resolve().parent.parent


def silk(board):
    for n in range(1,9):
        for k in (14,15,16):
            fp=board.FindFootprintByReference(f'C{n}{k}')
            p=fp.GetPosition();x,y=pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
            field=fp.Reference();field.SetTextSize(V(.8,.8))
            field.SetTextThickness(pcbnew.FromMM(.12))
            field.SetPosition(V(x,y-7.7) if k!=16 else V(x+6.5,y))
            field.SetTextAngle(pcbnew.EDA_ANGLE(0 if k!=16 else 90,pcbnew.DEGREES_T))
        tp=board.FindFootprintByReference(f'TP{n+16}')
        p=tp.GetPosition();tp.Reference().SetPosition(V(pcbnew.ToMM(p.x),96))
    # JLC's published readable legend minimum is 1 mm height / 0.15 mm stroke.
    texts=[d for d in board.GetDrawings() if d.GetClass()=='PCB_TEXT']
    texts.extend(field for fp in board.GetFootprints() for field in fp.GetFields())
    for text in texts:
        if text.GetText()=='eswitch rev B':text.SetText('eswitch rev C')
        if text.GetLayer() not in (pcbnew.F_SilkS,pcbnew.B_SilkS) or not text.IsVisible():continue
        size=text.GetTextSize()
        text.SetTextSize(pcbnew.VECTOR2I(max(size.x,pcbnew.FromMM(1)),max(size.y,pcbnew.FromMM(1))))
        text.SetTextThickness(max(text.GetTextThickness(),pcbnew.FromMM(.15)))


def main():
    path=ROOT/'eswitch.kicad_pcb';b=pcbnew.LoadBoard(str(path))
    sync_metadata(b,NETLIST)
    for ref in ('J4','U10'):
        for pad in b.FindFootprintByReference(ref).Pads():
            if pad.GetAttribute()==pcbnew.PAD_ATTRIB_PTH:
                s,d=pad.GetSize(),pad.GetDrillSize()
                pad.SetSize(pcbnew.VECTOR2I(max(s.x,d.x+pcbnew.FromMM(.52)),max(s.y,d.y+pcbnew.FromMM(.52))))
    silk(b)
    apply_rules(b);fill_zones(b);save_board(path,b);persist_project_rules(path)
    import re
    data,count=re.subn(r'\(paper "[^"]+"\)', '(paper "A2")',path.read_text(),count=1)
    assert count==1
    path.write_text(data)
    print('Revision C metadata, plated lands and silk updated; rerun native DRC')


if __name__=='__main__':main()
