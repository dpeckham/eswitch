#!/usr/bin/env python3
"""Staggered fine-pitch VIN and charge-pump escapes for U13."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals16.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-usb-escapes.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    for t in list(b.GetTracks()):
        net=short_name(t)
        if net in ('DEN7','DEN5','IN8') or (net=='VIN' and t.GetClass()=='PCB_TRACK' and t.GetLayer()==pcbnew.B_Cu
            and any(50<x<52 and 68<y<70 for x,y in (router.xy(t.GetStart()),router.xy(t.GetEnd())))):
            b.Remove(t);retired.append(t)
    for net,start,end in [('VIN',(51.5625,69.75),(50.8,69.95)),
                          ('VIN',(51.5625,68.75),(50.8,68.55)),
                          ('CAP_USB',(51.5625,69.25),(50.1,69.25)),
                          ('VIN',(54.4375,69.75),(55.2,70.05))]:
        t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/'+net));t.SetLayer(pcbnew.B_Cu)
        t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(.18));b.Add(t)
        v=pcbnew.PCB_VIA(b);v.SetNet(t.GetNet());v.SetPosition(V(*end))
        v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);b.Add(v)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output);print('Errors:',len(errors(r)),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
