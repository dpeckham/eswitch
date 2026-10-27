#!/usr/bin/env python3
"""Route the input TVS series path explicitly, outside the signal router."""
from route_checked import *
from shapely.geometry import LineString


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-clean2.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-clamps.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    for t in list(b.GetTracks()):
        if short_name(t)=='TVS_INPUT_MID':b.Remove(t);retired.append(t)
    for net,points in [('TVS_INPUT_MID',[(30,12.85),(33.5,12.85),(33.5,26.15),(30,26.15)]),
                       ('AUTO_FUSED',[(30,17.15),(27,17.15),(27,29),(33.8,29),(33.8,35)])]:
        corridor=LineString(points).buffer(1)
        for t in list(b.GetTracks()):
            if t.GetClass()!='PCB_TRACK' or t.GetLayer()!=pcbnew.F_Cu or short_name(t)!='AUTO_PROTECTED':continue
            if pcbnew.ToMM(t.GetWidth())>.5:continue
            shape=LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2)
            if corridor.intersects(shape):b.Remove(t);retired.append(t)
        for start,end in zip(points,points[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/'+net));t.SetLayer(pcbnew.F_Cu)
            t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(1.5));b.Add(t)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    print('Violations:',len(report['violations']),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
