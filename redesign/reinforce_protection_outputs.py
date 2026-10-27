#!/usr/bin/env python3
"""Parallel output copper between the selector and output PTH terminals."""
from route_checked import *
from shapely.geometry import LineString,Point


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-routed.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-output-copper.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    for original in list(b.Zones()):
        if original.GetIsRuleArea() or original.GetLayer()!=pcbnew.F_Cu or not short_name(original).startswith('LOAD'):continue
        z=pcbnew.ZONE(b);z.SetNet(original.GetNet());z.SetLayer(pcbnew.In2_Cu)
        z.SetAssignedPriority(2000+original.GetAssignedPriority());z.SetLocalClearance(pcbnew.FromMM(.25))
        z.SetMinThickness(pcbnew.FromMM(.25));z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        for i in range(original.Outline().OutlineCount()):
            outline=original.Outline().COutline(i)
            z.AddPolygon(pcbnew.VECTOR_VECTOR2I([outline.CPoint(j) for j in range(outline.PointCount())]))
        z.SetZoneName('protected_power_parallel_'+short_name(original));b.Add(z)
    displaced={}
    for n in range(1,9):
        net=f'LOAD{n}';cx=108+26*((n-1)%4)
        points=[(0,38.1),(10.5,38.1),(10.5,16),(3.81,16)]
        points=[(cx-x,116-y) if n>4 else (cx+x,y) for x,y in points]
        corridor=LineString(points).buffer(1.75+.25)
        for t in list(b.GetTracks()):
            other=short_name(t)
            if other==net:continue
            if t.GetClass()=='PCB_VIA':shape=Point(router.xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(pcbnew.In2_Cu))/2)
            elif t.GetLayer()==pcbnew.In2_Cu:shape=LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2)
            else:continue
            if not corridor.intersects(shape):continue
            if other.startswith(('LOAD','PROFET_OUT','USB')) or other in ('BATT_RAW','AUTO_PROTECTED','AUTO_FUSED','PROTECTION_COMMON_SOURCE'):
                raise RuntimeError(f'{net} reinforcement intersects reserved {other}')
            displaced[other]=displaced.get(other,0)+1;b.Remove(t);retired.append(t)
        for start,end in zip(points,points[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/'+net));t.SetLayer(pcbnew.In2_Cu)
            t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(3.5));b.Add(t)
    print('Signal/ground segments displaced:',displaced)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output);print('Errors:',len(errors(r)),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
