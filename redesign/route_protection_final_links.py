#!/usr/bin/env python3
"""Explicit local ground, USB-enable and ADC escape connections."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals11.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-final-links.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    for t in list(b.GetTracks()):
        if short_name(t) in ('DENR8','IS6'):
            b.Remove(t);retired.append(t)
    routes=[('GND',[(190.5625,67.45),(189.4,67.45)],.2,True),
            ('IS4',[(56.75,13.15),(57.95,13.15),(57.95,16.35)],.18,True)]
    for net,points,width,add_via in routes:
        for start,end in zip(points,points[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetNet(b.FindNet('/'+net));t.SetLayer(pcbnew.B_Cu)
            t.SetStart(V(*start));t.SetEnd(V(*end));t.SetWidth(pcbnew.FromMM(width));b.Add(t)
        if add_via:
            v=pcbnew.PCB_VIA(b);v.SetNet(b.FindNet('/'+net));v.SetPosition(V(*points[-1]))
            v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);b.Add(v)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    print('Errors:',len(errors(report)),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
