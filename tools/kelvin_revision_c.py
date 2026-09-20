#!/usr/bin/env python3
"""Keep sensitive test pads at their circuits; rebuild the main Kelvin pair."""
import argparse
from pathlib import Path
import pcbnew
from gen_pcb import V,apply_rules
from pcb_nets import find_net,short_name
from pcb_io import save_board,fill_zones
from sexp import parse_one,find,find_all,dump

ROOT=Path(__file__).resolve().parent.parent


def prepare(path):
    """Replace sensitive-net copper as text before creating any SWIG objects."""
    names={'HS_VCC','HS_SENSE','HS_TIMER','HGATE_MAIN'}
    doc=parse_one(Path(path).read_text())
    doc[:]=[item for item in doc if not (isinstance(item,list) and item and
        item[0] in ('segment','via') and short_name(find(item,'net')[1]) in names)]
    old=parse_one((ROOT/'out/revision-c-baseline/eswitch.kicad_pcb').read_text())
    doc.extend(item for item in find_all(old,'segment')+find_all(old,'via')
               if short_name(find(item,'net')[1]) in ('HS_TIMER','HGATE_MAIN'))
    temporary=ROOT/'out/kelvin-input.kicad_pcb'
    temporary.write_text(dump(doc)+'\n')
    return temporary


def apply(board):
    def route(net,layer,points):
        for a,b in zip(points,points[1:]):
            t=pcbnew.PCB_TRACK(board);t.SetStart(V(*a));t.SetEnd(V(*b))
            t.SetWidth(pcbnew.FromMM(.2));t.SetLayer(layer);t.SetNet(find_net(board,net));board.Add(t)
    def via(net,point):
        v=pcbnew.PCB_VIA(board);v.SetPosition(V(*point));v.SetWidth(pcbnew.FromMM(.55))
        v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
        v.SetNet(find_net(board,net));v.SetIsFree(True);board.Add(v)
    for ref,xy in [('TP4',(75.5,27.5)),('TP5',(79,27.5)),('TP6',(82.7,44.7)),('TP7',(104,28))]:
        fp=board.FindFootprintByReference(ref);fp.SetPosition(V(*xy))
        fp.Reference().SetPosition(V(xy[0],xy[1]+1.65))
    F,B=pcbnew.F_Cu,pcbnew.B_Cu
    for net,x,spine,ybend,xend,pinx in [('HS_VCC',69.975,77,34,87.1,86.45),
                                     ('HS_SENSE',78.025,77.45,33.55,85.8,85.8)]:
        route(net,B,[(x,20.5),(x,22.5)]);via(net,(x,22.5))
        firsty=24 if net=='HS_VCC' else 24.45
        route(net,F,[(x,22.5),(x,firsty),(spine,firsty),(spine,ybend),(xend,ybend),(xend,29.4)])
        via(net,(xend,29.4));route(net,B,[(xend,29.4),(pinx,30.45),(pinx,31.6375)])
    route('HS_VCC',F,[(75.5,27.5),(77,27.5)])
    route('HS_SENSE',F,[(79,27.5),(77.45,27.5)])
    route('HS_TIMER',B,[(82.95,40),(82.95,42)]);via('HS_TIMER',(82.95,42))
    route('HS_TIMER',F,[(82.95,42),(80.5,42),(80.5,50)])
    route('HS_TIMER',F,[(82.7,44.7),(80.5,44.7)])
    for y in (46,50):
        route('HS_TIMER',B,[(78.95,y),(80.5,y)]);via('HS_TIMER',(80.5,y))
    route('HGATE_MAIN',B,[(101.325,20),(103.5,20)]);via('HGATE_MAIN',(103.5,20))
    route('HGATE_MAIN',F,[(103.5,20),(104,20.5),(104,28)])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',default=str(ROOT/'eswitch.kicad_pcb'))
    args=p.parse_args();temporary=prepare(args.board);b=pcbnew.LoadBoard(str(temporary))
    apply(b);apply_rules(b);fill_zones(b);save_board(args.board,b)
