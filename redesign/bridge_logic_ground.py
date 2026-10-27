#!/usr/bin/env python3
"""Bridge the logic ground island around the raw-feed corridor."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-reinforced.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-ground-bridge.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    for t in list(b.GetTracks()):
        if short_name(t)=='IS8':b.Remove(t);retired.append(t)
    net=b.FindNet('/GND');points=[(60.35,10.6),(64.5,10.6),(64.5,15.2)]
    for start,end in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetNet(net);t.SetLayer(pcbnew.B_Cu)
        t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(.2));b.Add(t)
    v=pcbnew.PCB_VIA(b);v.SetNet(net);v.SetPosition(t.GetEnd())
    v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);b.Add(v)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output);print('Errors:',len(errors(r)),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
