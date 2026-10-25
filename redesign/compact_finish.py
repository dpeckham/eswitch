#!/usr/bin/env python3
"""Local escapes and ground-island stitching for the two-bank candidate."""
from route_checked import *


def inside(x,y,points):
    result=False
    previous=points[-1]
    for current in points:
        ax,ay=previous;bx,by=current
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:result=not result
        previous=current
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--board',type=Path,default=OUT/'compact-routed.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'compact-escaped.kicad_pcb')
    a=p.parse_args()
    b=pcbnew.LoadBoard(str(a.board));apply_rules(b)
    router.W,router.H=136.,104.
    router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
    router.SIZE=router.NX*router.NY
    report=json.loads(a.board.with_suffix('.summary.json').read_text())
    objects=items_by_id(b);removed=[]
    for v in report['violations']:
        if v['type'] in ('via_dangling','track_dangling'):
            for entry in v['items']:
                item=objects[entry['uuid']];b.Remove(item);removed.append(item)
    fps={fp.GetReference():fp for fp in b.GetFootprints()}
    def pad(ref,pin):return next(p for p in fps[ref].Pads() if p.GetNumber()==pin)
    missing={i['uuid'] for gap in report['unconnected_items'] for i in gap['items']}
    reopen_den4=pad('U4','4').m_Uuid.AsString() in missing
    if reopen_den4:
        for item in list(b.GetTracks()):
            if short_name(item)=='DENR4':b.Remove(item);removed.append(item)
    for n in range(1,9):
        cx=64+18*((n-1)%4)
        def xy(dx,y):return (cx-dx,104-y) if n>4 else (cx+dx,y)
        # Keep the front heat spreader and In2 copper; clear the back-side input
        # pin escape area below the broad VS fuse landing.
        for z in b.Zones():
            if z.GetIsRuleArea() or z.GetLayer() not in (pcbnew.B_Cu,pcbnew.In2_Cu) or short_name(z)!=f'VS{n}':continue
            z.Outline().RemoveAllContours()
            z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(*xy(x,y)) for x,y in
                [(-8,13),(1.4,13),(1.4,28.8),(-1.4,28.8),(-1.4,21.8),(-8,21.8)]]))
        for pin,dx,y in (('4',-4.5,25),('3',-4.,25.65)):
            terminal=pad(f'U{n}',pin)
            if terminal.m_Uuid.AsString() not in missing and not (reopen_den4 and n==4 and pin=='3'):continue
            net=terminal.GetNet()
            v=pcbnew.PCB_VIA(b);v.SetPosition(V(*xy(dx,y)));v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3))
            v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(net);b.Add(v)
            t=pcbnew.PCB_TRACK(b);t.SetStart(terminal.GetPosition());t.SetEnd(V(*xy(dx,y)))
            t.SetLayer(pcbnew.B_Cu);t.SetWidth(pcbnew.FromMM(.2));t.SetNet(net);b.Add(t)
        net=b.FindNet(f'/LEDK{n}')
        # This escape cuts only a small portion of the back spreader. F/In2
        # remain continuous, and the five-mm back strip stays joined beside it.
        if not any(t.GetNetCode()==net.GetNetCode() for t in b.GetTracks()):
            v=pcbnew.PCB_VIA(b);v.SetPosition(V(*xy(8.2,28.6)));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
            v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(net);b.Add(v)
            paths=[(pcbnew.F_Cu,[router.xy(pad(f'D{n}02','2').GetPosition()),xy(8.2,28.6)]),
                   (pcbnew.B_Cu,[xy(8.2,28.6),xy(8.2,32),router.xy(pad(f'R{n}07','2').GetPosition())]),
                   (pcbnew.B_Cu,[xy(8.2,28.6),xy(8.2,25.95),router.xy(pad(f'D{n}03','2').GetPosition())])]
            for layer,points in paths:
                for start,end in zip(points,points[1:]):
                    t=pcbnew.PCB_TRACK(b);t.SetStart(V(*start));t.SetEnd(V(*end));t.SetLayer(layer)
                    t.SetWidth(pcbnew.FromMM(.2));t.SetNet(net);b.Add(t)
    # Add one via per unstitched filled ground island, preserving all keepouts
    # and foreign pad/track clearances. Discard stale fills before serialization.
    gnd=b.FindNet('/GND')
    _,blocked=router.obstacles(AliasBoard(b),gnd.GetNetCode(),.25,.6)
    plane=next(z for z in b.Zones() if not z.GetIsRuleArea() and z.GetLayer()==pcbnew.In1_Cu and z.GetNetCode()==gnd.GetNetCode())
    reference=plane.GetFilledPolysList(pcbnew.In1_Cu)
    existing=[router.xy(t.GetPosition()) for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetCode()==gnd.GetNetCode()]
    count=0
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetCode()!=gnd.GetNetCode() or z.GetLayer()==pcbnew.In1_Cu:continue
        filled=z.GetFilledPolysList(z.GetLayer())
        for i in range(filled.OutlineCount()):
            o=filled.COutline(i);points=[router.xy(o.CPoint(j)) for j in range(o.PointCount())]
            if any(inside(x,y,points) and filled.Contains(V(x,y)) and reference.Contains(V(x,y)) for x,y in existing):continue
            found=False
            for iy in range(math.ceil(min(y for x,y in points)*5),math.floor(max(y for x,y in points)*5)+1):
                if found:break
                for ix in range(math.ceil(min(x for x,y in points)*5),math.floor(max(x for x,y in points)*5)+1):
                    x,y=ix/5,iy/5
                    if not reference.Contains(V(x,y)) or blocked[round(y/router.STEP)*router.NX+round(x/router.STEP)]:continue
                    if not all(inside(x+.32*math.cos(a*math.pi/4),y+.32*math.sin(a*math.pi/4),points)
                               and filled.Contains(V(x+.32*math.cos(a*math.pi/4),y+.32*math.sin(a*math.pi/4))) for a in range(8)):continue
                    if any(math.hypot(x-ax,y-ay)<.9 for ax,ay in existing):continue
                    v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
                    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(gnd);b.Add(v)
                    existing.append((x,y));count+=1;found=True;break
    a.output.with_suffix('.kicad_pro').write_text(a.board.with_suffix('.kicad_pro').read_text())
    result=check(b,a.output)
    a.output.with_suffix('.summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Island vias:',count,'Gaps:',len(result['unconnected_items']),'Violations:',result['violations'])


if __name__=='__main__':main()
