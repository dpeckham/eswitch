#!/usr/bin/env python3
"""Tie rear decoupling spreaders and the local TVS to the protected inner bus."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals10.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-decoupled.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));fps={f.GetReference():f for f in b.GetFootprints()}
    def via(x,y,diameter=.6,drill=.3):
        v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(pcbnew.FromMM(diameter));v.SetDrill(pcbnew.FromMM(drill))
        v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(b.FindNet('/AUTO_PROTECTED'));b.Add(v)
    for n in range(1,9):
        pad=next(p for p in fps[f'C{n}01'].Pads() if short_name(p)=='AUTO_PROTECTED')
        via(*router.xy(pad.GetPosition()))
    pad=next(p for p in fps['D10'].Pads() if short_name(p)=='AUTO_PROTECTED')
    x,y=router.xy(pad.GetPosition())
    for dx in (-.6,.6):
        for dy in (-.4,.4):via(x+dx,y+dy,.8,.4)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    print('Errors:',len(errors(report)),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
