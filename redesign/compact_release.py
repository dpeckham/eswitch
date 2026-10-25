#!/usr/bin/env python3
"""Prepare the fully routed compact board for final native parity checks."""
from route_checked import *

source=OUT/'compact-complete.kicad_pcb'
target=OUT/'compact-release.kicad_pcb'
b=pcbnew.LoadBoard(str(source));apply_rules(b)
report=json.loads(source.with_suffix('.summary.json').read_text())
assert not errors(report) and not report['unconnected_items']
objects=items_by_id(b);removed=[]
for v in report['violations']:
    assert v['type']=='via_dangling',v
    for entry in v['items']:
        item=objects[entry['uuid']];b.Remove(item);removed.append(item)
def label(text,x,y,layer=pcbnew.F_SilkS,angle=0):
    t=pcbnew.PCB_TEXT(b);t.SetText(text);t.SetPosition(V(x,y));t.SetLayer(layer)
    t.SetTextSize(V(.8,.8));t.SetTextThickness(pcbnew.FromMM(.12))
    t.SetTextAngle(pcbnew.EDA_ANGLE(angle,pcbnew.DEGREES_T));t.SetMirrored(layer==pcbnew.B_SilkS);b.Add(t)
for n in range(1,9):
    cx=64+18*((n-1)%4)
    for text,dx in (('+',-5.2),('-',5.2)):
        label(text,cx-dx if n>4 else cx+dx,104-15.5 if n>4 else 15.5,angle=180 if n>4 else 0)
label('UPSTREAM BATTERY FUSE REQUIRED',28,95)
label('LOGIC MAX 2A',49,32,pcbnew.B_SilkS)
target.with_suffix('.kicad_pro').write_text(source.with_suffix('.kicad_pro').read_text())
r=check(b,target)
assert not r['violations'] and not r['unconnected_items'],r['violations']
print('Compact release candidate: zero DRC violations and zero unconnected nets')
