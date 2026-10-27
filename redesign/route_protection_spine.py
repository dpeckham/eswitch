#!/usr/bin/env python3
"""Expand the protected-feed corridor around existing signal/reference guards."""
from route_checked import *
from shapely.geometry import Point, LineString


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-transfers.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-spine.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));apply_rules(b)
    retired=[]
    for z in b.Zones():
        if z.GetLayer()!=pcbnew.In2_Cu or z.GetZoneName()!='protected_power_AUTO_PROTECTED':continue
        if z.GetAssignedPriority()==403:
            points=[(27,94),(53,94),(53,51),(205,51),(205,65),(76,65),(76,107),(27,107)]
        elif z.GetAssignedPriority()==532:
            points=[(124,97),(106.6,97),(106.6,82),(111,82),(111,57),(124,57)]
        else:continue
        z.Outline().RemoveAllContours()
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(x,y) for x,y in points]))
    corridors=[([(31,100),(31,96),(64,96),(64,66),(72,58),(100,58)],8),
               ([(100,58),(198,58)],14)]
    for n in range(1,9):
        cx=108+26*((n-1)%4)
        corridors.append(([(cx-6,58),(cx-6,31),(cx,31)] if n<=4
                          else [(cx+6,58),(cx+6,85),(cx,85)],4))
    for points,width in corridors:
        corridor=LineString(points).buffer(width/2+.25)
        removed={}
        for t in list(b.GetTracks()):
            net=short_name(t)
            if net=='AUTO_PROTECTED':continue
            if t.GetClass()=='PCB_VIA':
                shape=Point(router.xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(pcbnew.In2_Cu))/2)
            elif t.GetLayer()==pcbnew.In2_Cu:
                shape=LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2)
            else:continue
            if corridor.intersects(shape):
                if net.startswith(('USB','LOAD','PROFET_OUT')) or net in ('BATT_RAW','AUTO_FUSED','PROTECTION_COMMON_SOURCE'):
                    raise RuntimeError(f'Power corridor conflicts with reserved {net}')
                removed[net]=removed.get(net,0)+1;b.Remove(t);retired.append(t)
        print('Segments/vias displaced:',removed)
        for start,end in zip(points,points[1:]):
            if any(t.GetClass()=='PCB_TRACK' and short_name(t)=='AUTO_PROTECTED'
                   and t.GetLayer()==pcbnew.In2_Cu and abs(pcbnew.ToMM(t.GetWidth())-width)<.001
                   and {tuple(router.xy(t.GetStart())),tuple(router.xy(t.GetEnd()))}=={tuple(start),tuple(end)}
                   for t in b.GetTracks()):continue
            t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/AUTO_PROTECTED'));t.SetLayer(pcbnew.In2_Cu)
            t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(width));b.Add(t)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    print('Violations:',len(report['violations']),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
