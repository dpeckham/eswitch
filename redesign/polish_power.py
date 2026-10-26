#!/usr/bin/env python3
"""Explicit diode-ground escapes and CH5 pull-down access for the expanded board."""
from route_checked import *


def main():
    p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.board));retired=[]
    fps={f.GetReference():f for f in b.GetFootprints()}
    for n in range(1,9):
        cx=72+26*((n-1)%4)
        position=V(cx-4.1,85) if n>4 else V(cx+4.1,31)
        via=pcbnew.PCB_VIA(b);via.SetPosition(position);via.SetWidth(pcbnew.FromMM(.5));via.SetDrill(pcbnew.FromMM(.3))
        via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);via.SetNet(b.FindNet('/GND'));b.Add(via)
        for pad in fps[f'D{n}03'].Pads():
            if short_name(pad)!='GND':continue
            t=pcbnew.PCB_TRACK(b);t.SetStart(pad.GetPosition());t.SetEnd(position)
            t.SetLayer(pcbnew.B_Cu);t.SetWidth(pcbnew.FromMM(.2));t.SetNet(pad.GetNet());b.Add(t)
    for ref,y in [('R508',67.8),('R509',65.3)]: fps[ref].SetPosition(V(84.5,y))
    for t in list(b.GetTracks()):
        if short_name(t) in ('INR5','DENR5','UGND5'):
            b.Remove(t);retired.append(t)
    a.output.with_suffix('.kicad_pro').write_text(a.board.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    a.output.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Violations:',report['violations'],'gaps:',len(report['unconnected_items']))


if __name__=='__main__': main()
