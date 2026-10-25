#!/usr/bin/env python3
"""Synchronize explicit NC-net metadata for native KiCad 10 schematic parity."""
from route_checked import *
from sexp import parse_one,find,find_all

target=HERE/'eswitch-simple.kicad_pcb'
b=pcbnew.LoadBoard(str(target));apply_rules(b)
doc=parse_one((OUT/'netlist.net').read_text())
fps={fp.GetReference():fp for fp in b.GetFootprints()}
for entry in find_all(find(doc,'nets'),'net'):
    name=find(entry,'name')[1]
    if not name.startswith('unconnected-'):continue
    net=b.FindNet(name)
    if not net:
        net=pcbnew.NETINFO_ITEM(b,name);b.Add(net)
    for node in find_all(entry,'node'):
        ref,pin=find(node,'ref')[1],find(node,'pin')[1]
        for pad in fps[ref].Pads():
            if pad.GetNumber()==pin:pad.SetNet(net)
for z in b.Zones():
    if not z.GetIsRuleArea():z.UnFill()
if not any(item.GetClass()=='PCB_DIM_ALIGNED' for item in b.GetDrawings()):
    bounds=b.GetBoardEdgesBoundingBox()
    width,height=round(pcbnew.ToMM(bounds.GetWidth())),round(pcbnew.ToMM(bounds.GetHeight()))
    for start,end in (((0,height),(width,height)),((width,height),(width,0))):
        dim=pcbnew.PCB_DIM_ALIGNED(b)
        dim.SetLayer(pcbnew.Dwgs_User)
        dim.SetStart(V(*start));dim.SetEnd(V(*end));dim.SetHeight(pcbnew.FromMM(6))
        dim.SetUnitsMode(pcbnew.DIM_UNITS_MODE_MM)
        dim.SetUnitsFormat(pcbnew.DIM_UNITS_FORMAT_BARE_SUFFIX)
        dim.SetPrecision(1);dim.SetTextSize(V(1.5,1.5));dim.SetLineThickness(pcbnew.FromMM(.15))
        dim.Update();b.Add(dim)
save_board(target,b)
print('Explicit NC assignments synchronized:',target)
