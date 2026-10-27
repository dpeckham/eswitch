#!/usr/bin/env python3
"""Final local LED and ground connections for the parallel output rework."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-output-clean.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-output-links.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source))
    points=[(100.5625,84.05),(99.1,84.05),(99.1,86.7875),(100,86.7875)]
    for start,end in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/LEDK5'));t.SetLayer(pcbnew.B_Cu)
        t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(.18));b.Add(t)
    v=pcbnew.PCB_VIA(b);v.SetNet(b.FindNet('/GND'));v.SetPosition(V(104.8,44.4))
    v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);b.Add(v)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output);print('Errors:',len(errors(r)),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
