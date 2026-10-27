#!/usr/bin/env python3
"""Local pad escapes around the protected inner-layer channel feeds."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-ground-routed.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-escapes.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    # These previously routed nets close off the neighboring pad escape lanes.
    # Re-route them after reserving the short, fine-pitch fanout below.
    for t in list(b.GetTracks()):
        if short_name(t) in ('VS_CONTROLLER','ISP6','ISP8','DEN7'):
            b.Remove(t);retired.append(t)
    routes=[('HGATE_AUTO',[(13.4375,44.25),(13.8,44.25),(14.5,43.9)]),
            ('GND',[(13.4375,43.75),(13.4375,42.8)])]
    for n in (6,8):
        x=108+26*((n-1)%4)
        routes.append((f'DENR{n}',[(x+2.85,84.35),(x+3.8,84.35),(x+3.8,82.2),(x+3.4,82.2)]))
        routes.append((f'ISP{n}',[(x+2.845,85),(x+3.8,85),(x+3.8,87.8),(x+2.8,87.8)]))
    for net,points in routes:
        for start,end in zip(points,points[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/'+net));t.SetLayer(pcbnew.B_Cu)
            t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(.18));b.Add(t)
        v=pcbnew.PCB_VIA(b);v.SetNet(b.FindNet('/'+net));v.SetPosition(V(*points[-1]))
        v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);b.Add(v)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    print('Errors:',len(errors(report)),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
