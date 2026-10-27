#!/usr/bin/env python3
"""Move the controller below the raw-feed corridor before final signal routing."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals8.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-controller.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    local={'VS_CONTROLLER','CAP_AUTO','OV_AUTO','OV_DIV_MID','HGATE_AUTO','DGATE_AUTO'}
    for t in list(b.GetTracks()):
        net=short_name(t)
        ends=[router.xy(t.GetPosition())] if t.GetClass()=='PCB_VIA' else [router.xy(t.GetStart()),router.xy(t.GetEnd())]
        small=t.GetClass()=='PCB_VIA' or pcbnew.ToMM(t.GetWidth())<=.5
        branch=net in ('GND','AUTO_FUSED','AUTO_PROTECTED','PROTECTION_COMMON_SOURCE') and small and any(x<30 and y<36 for x,y in ends)
        if net in local or branch:
            b.Remove(t);retired.append(t)
    locations={'U15':(12,45),'C26':(12,52),'C27':(17,45),'C28':(22,42),
               'R27':(6,45),'R28':(6,49),'R29':(6,53),'D8':(6,38),'D9':(20,50)}
    for f in b.GetFootprints():
        if f.GetReference() in locations:f.SetPosition(V(*locations[f.GetReference()]))
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    print('Violations:',len(report['violations']),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
