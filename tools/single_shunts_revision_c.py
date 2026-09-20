#!/usr/bin/env python3
"""Replace series shunt chains with one exact-value shunt and local Kelvin routes."""
import argparse
from pathlib import Path
import pcbnew
from sexp import parse_one,find,find_all,dump,Sym
from gen_pcb import Board,V,read_netlist,NETLIST,apply_rules
from pcb_nets import short_name,sync_metadata
from pcb_io import save_board,fill_zones
import revision_c as rev

ROOT=Path(__file__).resolve().parent.parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--board',default=str(ROOT/'eswitch.kicad_pcb'))
    args=p.parse_args();path=Path(args.board)
    doc=parse_one(path.read_text())
    baseline=parse_one((ROOT/'out/revision-c-baseline/eswitch.kicad_pcb').read_text())
    preserved={find(t,'uuid')[1] for t in find_all(baseline,'segment')+find_all(baseline,'via')}
    def remove(t):
        if not isinstance(t,list) or not t:return False
        if t[0]=='footprint':
            ref=next(v[2] for v in find_all(t,'property') if v[1]=='Reference')
            return ref in {f'R{n}2{k}' for n in range(1,9) for k in range(4)}
        if t[0] in ('segment','via'):
            net=short_name(find(t,'net')[1]);uid=find(t,'uuid')[1]
            if net.startswith('BR_R'):return True
            if t[0]=='segment' and net.startswith('BR_SENSE'):return True
            if net=='+12V' and uid not in preserved and t[0]=='segment' and min(
                    float(find(t,key)[1]) for key in ('start','end'))>=118:return True
        return False
    doc[:]=[t for t in doc if not remove(t)]
    # Keep the high-current feeder on B.Cu to the shunt. F/In2 end before
    # the Kelvin pickup, so the sense trace is not merged into a feeder pour.
    for z in find_all(doc,'zone'):
        if not find(z,'net') or short_name(find(z,'net')[1])!='+12V':continue
        poly=find(z,'polygon')
        if not poly:continue
        pts=find_all(find(poly,'pts'),'xy');xs=[float(a[1]) for a in pts];ys=[float(a[2]) for a in pts]
        for n,x in enumerate(rev.CX,1):
            if abs(min(xs)-(x-.1))<.01 and abs(max(xs)-(x+4.1))<.01 and abs(min(ys)-30)<.01:
                top=61.5-(2.855 if rev.SHUNT_MOHM[n]==8 else 2.16)
                end=top+1 if find(z,'layer')[1]=='B.Cu' else top-2.5
                for a in pts:
                    if abs(float(a[2])-max(ys))<.01:a[2]=Sym(str(end))
    temporary=ROOT/'out/single-shunts-input.kicad_pcb';temporary.write_text(dump(doc)+'\n')
    b=pcbnew.LoadBoard(str(temporary));bd=Board.__new__(Board);bd.b=b
    bd.comps,bd.netlist=read_netlist(NETLIST);bd.nets={short_name(net):net for net in b.GetNetsByName().values()}
    bd.pad_net={(ref,pin):short_name(net) for net,nodes in bd.netlist.items() for ref,pin in nodes}
    bd.fps={fp.GetReference():fp for fp in b.GetFootprints()}
    for n,x in enumerate(rev.CX,1):
        ref=f'R{n}20';fp=bd.place(ref,x+2,61.5,90,'B');bd.pin_up(ref)
        fp.Reference().SetVisible(False)
        for pad in fp.Pads():pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        a=bd.pad_pos(ref,'1');d=bd.pad_pos(ref,'2')
        for xx in (x+.6,x+2,x+3.4):
            for yy in (a[1]-4,a[1]-2.8):
                if not any(t.GetClass()=='PCB_VIA' and (t.GetPosition()-V(xx,yy)).EuclideanNorm()<pcbnew.FromMM(.65) for t in b.GetTracks()):
                    bd.via('+12V',xx,yy,.8,.4)
        # Escape the two adjacent left-side controller pins to F.Cu together.
        u=f'U{20+n}';vp=bd.pad_pos(u,'14');sp=bd.pad_pos(u,'13')
        v=(x-12.6,60.4);s=(x-11.9,61.2)
        bd.track(pcbnew.B_Cu,'+12V',[vp,(x-11.45,60.55),v],.2)
        bd.track(pcbnew.B_Cu,f'BR_SENSE{n}',[sp,s],.2)
        for net,pnt in [('+12V',v),(f'BR_SENSE{n}',s),('+12V',a),(f'BR_SENSE{n}',d)]:
            bd.via(net,*pnt,.55,.3)
        bd.track(pcbnew.F_Cu,'+12V',[v,(a[0],v[1]),a],.2)
        bd.track(pcbnew.F_Cu,f'BR_SENSE{n}',[s,(d[0],s[1]),d],.2)
    sync_metadata(b,NETLIST);apply_rules(b);fill_zones(b);save_board(path,b)
    print('Single shunts and local Kelvin pairs applied; native DRC required')


if __name__=='__main__':main()
