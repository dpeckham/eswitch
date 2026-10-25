#!/usr/bin/env python3
"""Finish compact ground-pad access and add escapes for remaining signals."""
from route_checked import *

source=OUT/'compact-routed3.kicad_pcb';target=OUT/'compact-last.kicad_pcb'
b=pcbnew.LoadBoard(str(source));apply_rules(b)
removed=[]
# Reopen the 3V3 segment crossing the only direct C9 ground-via site.
for item in list(b.GetTracks()):
    if item.GetClass()=='PCB_TRACK' and short_name(item)=='+3V3' and item.GetLayer()==pcbnew.F_Cu:
        start,end=router.xy(item.GetStart()),router.xy(item.GetEnd())
        if abs(start[0]-23.8)<.001 and abs(end[0]-23.8)<.001 and abs(start[1]-end[1])>10:
            b.Remove(item);removed.append(item)
fps={fp.GetReference():fp for fp in b.GetFootprints()}
def pad(ref,pin):return next(p for p in fps[ref].Pads() if p.GetNumber()==pin)
def via(net,point):
    if any(t.GetClass()=='PCB_VIA' and t.GetPosition()==point for t in b.GetTracks()):return
    v=pcbnew.PCB_VIA(b);v.SetPosition(point);v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3))
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(net);b.Add(v)
def track(net,start,end,layer):
    t=pcbnew.PCB_TRACK(b);t.SetStart(start);t.SetEnd(end);t.SetLayer(layer)
    t.SetWidth(pcbnew.FromMM(.18));t.SetNet(net);b.Add(t)
for n in range(1,9):
    p=pad(f'D{n}02','1');cx=64+18*((n-1)%4)
    point=V(cx-4.7,104-30.7875) if n>4 else V(cx+4.7,30.7875)
    via(p.GetNet(),point);track(p.GetNet(),p.GetPosition(),point,pcbnew.F_Cu)
for ref in ('R503','R603','R703','R104','C9','C203','R206'):
    p=pad(ref,'2');x,y=router.xy(p.GetPosition())
    if ref=='C9':
        via(p.GetNet(),p.GetPosition())
        continue
    dx=.2 if ref in ('R503','R603','R703') else .6 if ref=='C9' else 0
    dy=.9 if ref=='C9' else 0
    via(p.GetNet(),V(x+dx,y+dy))
    if ref=='C9':track(p.GetNet(),p.GetPosition(),V(x+dx,y+dy),pcbnew.B_Cu)
for p in fps['U10'].Pads():
    if short_name(p) in ('IS1','DEN1','DEN5','DEN6'):
        x,y=router.xy(p.GetPosition())
        point=V(8.5,21.2) if short_name(p)=='DEN1' else V(4.5,y)
        via(p.GetNet(),point);track(p.GetNet(),p.GetPosition(),point,pcbnew.B_Cu)
for ref,pin in [('R102','1'),('R502','1'),('R602','1'),
                ('U2','1'),('U3','1'),('R208','2'),('R308','2')]:
    p=pad(ref,pin);x,y=router.xy(p.GetPosition())
    point=V(x,y+.15) if ref in ('U2','U3') else V(x+.7,y) if ref=='R102' else p.GetPosition()
    via(p.GetNet(),point)
    if ref=='R102':track(p.GetNet(),p.GetPosition(),point,pcbnew.B_Cu)
target.with_suffix('.kicad_pro').write_text(source.with_suffix('.kicad_pro').read_text())
r=check(b,target)
target.with_suffix('.summary.json').write_text(json.dumps(r,indent=2)+'\n')
print('Gaps',len(r['unconnected_items']),'Errors',errors(r))
