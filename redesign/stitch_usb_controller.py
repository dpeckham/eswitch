#!/usr/bin/env python3
"""Explicit ground escapes for the relocated USB controller's two ground pads."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals15.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-usb-ground.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    for t in list(b.GetTracks()):
        net=short_name(t)
        if net=='DEN7' or (net=='VBUS' and t.GetClass()=='PCB_TRACK' and t.GetLayer()==pcbnew.B_Cu
                         and any(50<x<57 and 67<y<73 for x,y in (router.xy(t.GetStart()),router.xy(t.GetEnd())))):
            b.Remove(t);retired.append(t)
    f=next(f for f in b.GetFootprints() if f.GetReference()=='U13')
    for pad in f.Pads():
        if short_name(pad)!='GND':continue
        x,y=router.xy(pad.GetPosition());end=(x+(.9 if x>53 else -.9),y)
        t=pcbnew.PCB_TRACK(b);t.SetNet(pad.GetNet());t.SetLayer(pcbnew.B_Cu)
        t.SetStart(pad.GetPosition());t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(.18));b.Add(t)
        v=pcbnew.PCB_VIA(b);v.SetNet(pad.GetNet());v.SetPosition(V(*end))
        v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);b.Add(v)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output);print('Errors:',len(errors(r)),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
