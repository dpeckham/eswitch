#!/usr/bin/env python3
"""Refine the routed power candidate and stitch disconnected filled islands."""
from power_geometry import *


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('board',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--refine',action='store_true')
    parser.add_argument('--cleanup',action='store_true')
    parser.add_argument('--clear-root',action='store_true')
    parser.add_argument('--reopen-final',action='store_true')
    a=parser.parse_args()
    source=a.board
    if a.cleanup:
        assert a.board.resolve()!=a.output.resolve(), 'Use a separate candidate path'
        shutil.copyfile(a.board,a.output)
        shutil.copyfile(a.board.with_suffix('.kicad_pro'),a.output.with_suffix('.kicad_pro'))
        subprocess.run([sys.executable,str(HERE/'prune_power.py'),str(a.output)],check=True)
        source=a.output
    b=pcbnew.LoadBoard(str(source)); retired=[]
    if a.reopen_final:
        for t in list(b.GetTracks()):
            if short_name(t) in ('DEN2','DEN4','IS5','ADC_CLAMP_2V5'):
                b.Remove(t);retired.append(t)
        # Clamp-ground vias at the outer edge of the pad/feed, away from the
        # feed elbow. This preserves the connected-width floor through the elbow.
        for cx in (72,98,124,150):
            v=pcbnew.PCB_VIA(b);v.SetPosition(V(cx-4.3,48.55))
            v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3))
            v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(b.FindNet('/GND'));b.Add(v)
    if a.clear_root:
        from shapely.geometry import box
        root=box(45,34,58,50)
        for t in list(b.GetTracks()):
            if t.GetClass()=='PCB_TRACK' and short_name(t)=='IS5' and t.GetLayer()==pcbnew.In2_Cu and LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).intersects(root):
                b.Remove(t);retired.append(t)
    title=b.GetTitleBlock();title.SetRevision('DRAFT-PWR2');title.SetDate('2026-10-26');b.SetTitleBlock(title)
    if not any(d.GetClass()=='PCB_TEXT' and d.GetText().startswith('PWR2:') for d in b.GetDrawings()):
        text=pcbnew.PCB_TEXT(b);text.SetText('PWR2: 1=LOAD+ 2=GND');text.SetPosition(V(26,109))
        text.SetLayer(pcbnew.F_SilkS);text.SetTextSize(V(.8,.8));text.SetTextThickness(pcbnew.FromMM(.12));b.Add(text)
    if a.cleanup:
        for z in b.Zones():
            if not z.GetIsRuleArea():
                z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
                if short_name(z)=='GND': z.SetMinThickness(pcbnew.FromMM(.3))
    for d in list(b.GetDrawings()):
        if d.GetLayer()==pcbnew.Edge_Cuts: b.Remove(d);retired.append(d)
    perimeter=[(0,6),(36,6),(36,0),(176,0),(176,116),(0,116),(0,6)]
    for start,end in zip(perimeter,perimeter[1:]):
        d=pcbnew.PCB_SHAPE(b);d.SetShape(pcbnew.SHAPE_T_SEGMENT)
        d.SetStart(V(*start));d.SetEnd(V(*end));d.SetLayer(pcbnew.Edge_Cuts)
        d.SetWidth(pcbnew.FromMM(.05));b.Add(d)
    for z in b.Zones():
        if z.GetIsRuleArea() or short_name(z)!='BATT_RAW': continue
        priority=z.GetAssignedPriority()
        if priority==2:
            points=[(37,18),(67,18),(67,34),(58,34),(58,46),(65,46),(65,50),(169,50),(169,66),(55,66),(45,50),(45,34),(37,34)]
        elif 7<=priority<=14:
            n=priority-6;cx=72+26*((n-1)%4)
            points=[(cx-x,110-y) if n>4 else (cx+x,y+6) for x,y in
                    [(-7.5,29.5),(1.4,29.5),(1.4,39),(-3.3,39),(-3.3,53),(-9.5,53),(-9.5,39),(-7.5,37)]]
        else: continue
        z.Outline().RemoveAllContours();z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(*p) for p in points]))
    if a.refine:
        for t in list(b.GetTracks()):
            if short_name(t)=='ADC_CLAMP_2V5': b.Remove(t);retired.append(t)
        for z in b.Zones():
            if z.GetIsRuleArea(): continue
            net=short_name(z)
            points=None
            if net.startswith('LOAD'):
                n=int(net[4:]);cx=72+26*((n-1)%4)
                points=[(cx-x,110-y) if n>4 else (cx+x,y+6) for x,y in
                        [(2,8.2),(11.5,8.2),(11.5,46.5),(-3.3,46.5),(-3.3,39.5),(2,39.5)]]
            elif net.startswith('VS') and z.GetLayer()!=pcbnew.F_Cu:
                n=int(net[2:]);cx=72+26*((n-1)%4)
                points=[(cx-x,110-y) if n>4 else (cx+x,y+6) for x,y in
                        [(-10,13),(1.4,13),(1.4,28.8),(-1.4,28.8),(-1.4,21.8),(-10,21.8)]]
            if points:
                z.Outline().RemoveAllContours();z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(*p) for p in points]))
    a.output.with_suffix('.kicad_pro').write_text(a.board.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    # Work from native fills. Add vias only where the complete annulus fits both
    # the island and the ground plane and the router's all-layer clearance mask.
    original=b;b=pcbnew.LoadBoard(str(a.output))
    router.W,router.H=176.,116.
    router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
    router.SIZE=router.NX*router.NY
    gnd=b.FindNet('/GND');_,blocked=router.obstacles(AliasBoard(b),gnd.GetNetCode(),.25,.6)
    plane=copper(b,'GND',pcbnew.In1_Cu)
    existing=[router.xy(t.GetPosition()) for t in b.GetTracks() if t.GetClass()=='PCB_VIA']
    count=0
    for z in b.Zones():
        if z.GetIsRuleArea() or short_name(z)!='GND' or z.GetLayer()==pcbnew.In1_Cu: continue
        for island in polygons(z.GetFilledPolysList(z.GetLayer())):
            # Already connected through a same-net plated hole or via?
            anchors=[router.xy(t.GetPosition()) for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and short_name(t)=='GND']
            anchors += [router.xy(p.GetPosition()) for f in b.GetFootprints() for p in f.Pads()
                        if short_name(p)=='GND' and p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH]
            if any(island.covers(Point(p)) for p in anchors): continue
            safe=island.intersection(plane).buffer(-.32)
            if safe.is_empty: continue
            x0,y0,x1,y1=safe.bounds; found=False
            for iy in range(math.ceil(y0*5),math.floor(y1*5)+1):
                if found: break
                for ix in range(math.ceil(x0*5),math.floor(x1*5)+1):
                    x,y=ix/5,iy/5
                    if not safe.covers(Point(x,y)) or blocked[round(y/router.STEP)*router.NX+round(x/router.STEP)]: continue
                    if any(math.hypot(x-u,y-v)<.9 for u,v in existing): continue
                    v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
                    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(gnd);b.Add(v)
                    existing.append((x,y));count+=1;found=True;break
    report=check(b,a.output)
    a.output.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Island stitches:',count,'violations:',len(report['violations']),'gaps:',len(report['unconnected_items']))


if __name__=='__main__': main()
