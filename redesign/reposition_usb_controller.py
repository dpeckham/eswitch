#!/usr/bin/env python3
"""Move the USB ideal-diode controller clear of the high-current corridor."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals12.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-usb-placed.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    for t in list(b.GetTracks()):
        net=short_name(t)
        ends=[router.xy(t.GetPosition())] if t.GetClass()=='PCB_VIA' else [router.xy(t.GetStart()),router.xy(t.GetEnd())]
        local=net in ('VIN','VBUS','GND') and any(58<x<64 and 58<y<64 for x,y in ends)
        if net in ('DGATE_USB','CAP_USB','IS5','DEN7') or local:
            b.Remove(t);retired.append(t)
    next(f for f in b.GetFootprints() if f.GetReference()=='U13').SetPosition(V(53,70))
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output);print('Errors:',len(errors(r)),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
