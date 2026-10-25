#!/usr/bin/env python3
"""Locate disconnected ground copper geometrically when DRC names only zones."""
from route_checked import *
from shapely.geometry import Polygon, Point, LineString

b=pcbnew.LoadBoard(sys.argv[1] if len(sys.argv)>1 else str(OUT/'escape.kicad_pcb'))
ground=b.FindNet('/GND').GetNetCode()
nodes=[]
for z in b.Zones():
    if z.GetIsRuleArea() or z.GetNetCode()!=ground:continue
    f=z.GetFilledPolysList(z.GetLayer())
    for i in range(f.OutlineCount()):
        def points(o):return [router.xy(o.CPoint(j)) for j in range(o.PointCount())]
        shape=Polygon(points(f.COutline(i)),[points(f.CHole(i,h)) for h in range(f.HoleCount(i))]).buffer(0)
        nodes.append((f'{z.GetZoneName()}:{i}',{z.GetLayer():shape}))
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetCode()!=ground:continue
        shapes={}
        for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]:
            if p.IsOnLayer(layer):
                from shapely.ops import unary_union
                shapes[layer]=unary_union([Polygon(points).buffer(0) for points in router.pad_polygons(p,layer)])
        nodes.append((f'{fp.GetReference()}.{p.GetNumber()}',shapes))
for t in b.GetTracks():
    if t.GetNetCode()!=ground:continue
    if t.GetClass()=='PCB_VIA':
        shape=Point(router.xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2)
        shapes={l:shape for l in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]}
    else:shapes={t.GetLayer():LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2)}
    nodes.append((t.GetClass()+str(router.xy(t.GetPosition())),shapes))
parents=list(range(len(nodes)))
def root(i):
    while parents[i]!=i:i=parents[i]
    return i
for i,(_,shapes) in enumerate(nodes):
    for j in range(i):
        if root(i)==root(j):continue
        if any(layer in nodes[j][1] and shape.intersects(nodes[j][1][layer]) for layer,shape in shapes.items()):
            parents[root(i)]=root(j)
groups={}
for i,node in enumerate(nodes):groups.setdefault(root(i),[]).append(node)
for group in sorted(groups.values(),key=len):
    print('GROUP',len(group))
    if len(group)<25:
        for name,shapes in group:print(name,{layer:shape.bounds for layer,shape in shapes.items()})
