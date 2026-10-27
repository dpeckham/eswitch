#!/usr/bin/env python3
"""Synchronize explicit NC-net metadata for native KiCad 10 schematic parity."""
from route_checked import *
from sexp import parse_one,find,find_all

p=argparse.ArgumentParser()
p.add_argument('--board',type=Path,default=HERE/'eswitch-simple.kicad_pcb')
p.add_argument('--output',type=Path)
p.add_argument('--netlist',type=Path,default=OUT/'netlist.net')
a=p.parse_args();target=a.output or a.board
if target!=a.board:
    target.with_suffix('.kicad_pro').write_text(a.board.with_suffix('.kicad_pro').read_text())
b=pcbnew.LoadBoard(str(a.board));apply_rules(b)
doc=parse_one(a.netlist.read_text())
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
            if pad.GetNumber()==pin:
                if pad.GetNetCode() and not pad.GetNetname().startswith('unconnected-'):
                    raise ValueError(f'{ref}.{pin} has a functional net; cannot assign NC metadata')
                pad.SetNet(net)
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
