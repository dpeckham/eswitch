#!/usr/bin/env python3
"""Keep indicator/ground transitions beside the parallel output corridors."""
from route_checked import *


class PlacementBoard(AliasBoard):
    def Zones(self):
        # Filled pours clear around the new lands. Preserve physical copper
        # tracks, pad/hole clearances, USB reference guards and rule areas.
        return [z for z in self.board.Zones() if z.GetIsRuleArea()]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals19.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-indicator-vias.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    bounds=b.GetBoardEdgesBoundingBox()
    router.W,router.H=round(pcbnew.ToMM(bounds.GetWidth())),round(pcbnew.ToMM(bounds.GetHeight()))
    router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
    router.SIZE=router.NX*router.NY
    for n in range(1,9):
        cx=108+26*((n-1)%4)
        def xy(x,y):return (cx-x,116-y) if n>4 else (cx+x,y)
        for t in list(b.GetTracks()):
            if t.GetClass()!='PCB_TRACK' or t.GetLayer()!=pcbnew.F_Cu:continue
            net=short_name(t);pts=[router.xy(t.GetStart()),router.xy(t.GetEnd())]
            local=[(cx-x,116-y) if n>4 else (x-cx,y) for x,y in pts]
            # Replace the front LED's old via escapes. Dn02 is the front LED;
            # Dn03 is the separate rear clamp and is not moved.
            if net==f'LEDK{n}' or (net=='GND' and all(4<x<12 and 34<y<40 for x,y in local)):
                b.Remove(t);retired.append(t)
        led=next(f for f in b.GetFootprints() if f.GetReference()==f'D{n}02')
        masks={}
        for net in ('GND',f'LEDK{n}'):
            masks[net]=router.obstacles(PlacementBoard(b),b.FindNet('/'+net).GetNetCode(),1.3,.5)
        positions=[(i*.5,j*.5) for i in range(2,45) for j in range(40,93)]
        positions.sort(key=lambda p:(p[0]-6.5)**2+(p[1]-36)**2)
        for x,y in positions:
            good=True
            for net,dy in [('GND',.7875),(f'LEDK{n}',-.7875)]:
                px,py=xy(x,y+dy);col,row=round(px/router.STEP),round(py/router.STEP)
                if not(0<=col<router.NX and 0<=row<router.NY):good=False;break
                index=row*router.NX+col;tracks,vias=masks[net]
                if tracks[index] or vias[index]:good=False;break
            if good:break
        else:raise RuntimeError(f'No physical LED/via placement found for CH{n}')
        print('LED placement',n,xy(x,y),flush=True)
        led.SetPosition(V(*xy(x,y)))
        for pad in led.Pads():
            v=pcbnew.PCB_VIA(b);v.SetNet(pad.GetNet());v.SetPosition(pad.GetPosition())
            v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);b.Add(v)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output);print('Errors:',len(errors(r)),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
