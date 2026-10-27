#!/usr/bin/env python3
"""Explicit high-current route candidate, checked by native KiCad after edits."""
from route_checked import *
from shapely.geometry import Point, LineString


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals4.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-power.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));apply_rules(b)
    retired=[]
    for z in list(b.Zones()):
        if z.GetZoneName()=='raw_input_bridge':
            b.Remove(z);retired.append(z)
    def outline(z,points):
        z.Outline().RemoveAllContours()
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(x,y) for x,y in points]))
    for z in b.Zones():
        if z.GetZoneName()=='protected_power_PROTECTION_COMMON_SOURCE':
            outline(z,[(19,32),(26,32),(26,90),(47,90),(47,105),(48,105),(48,110),(43,110),(43,96),(26,96),(26,101),(19,101)])
        if z.GetLayer()==pcbnew.B_Cu and z.GetZoneName().startswith('protected_power_PROFET_OUT'):
            n=int(short_name(z).replace('PROFET_OUT',''));cx=108+26*((n-1)%4)
            points=[(-3,21),(10,21),(10,35),(2,35),(2,27),(-3,27)]
            outline(z,[(cx-x,116-y) if n>4 else (cx+x,y) for x,y in points])
    def track(net,layer,points,width):
        for start,end in zip(points,points[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/'+net));t.SetLayer(layer)
            t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(width));b.Add(t)
    # Reserve an 8 mm inner-layer feed before rebuilding affected signal routes.
    # Both endpoints are multi-pin PTH terminals; no single-via power transfer.
    raw_path=[(12,19),(26,19),(26,10.7),(76,10.7),(76,26),(81,26)]
    corridor=LineString(raw_path).buffer(4.25)
    removed={}
    for t in list(b.GetTracks()):
        if short_name(t)=='BATT_RAW': continue
        if t.GetClass()=='PCB_VIA':
            shape=Point(router.xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(pcbnew.In2_Cu))/2)
        elif t.GetLayer()==pcbnew.In2_Cu:
            shape=LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2)
        else: continue
        if corridor.intersects(shape):
            net=short_name(t);removed[net]=removed.get(net,0)+1
            b.Remove(t);retired.append(t)
    print('Segments/vias removed for power-first rerouting:',removed)
    track('BATT_RAW',pcbnew.In2_Cu,raw_path,8)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    print('Violations:',len(report['violations']),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
