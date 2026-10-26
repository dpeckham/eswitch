#!/usr/bin/env python3
"""Build an expanded power-layout candidate from the saved compact board.

Never replaces the authoritative PCB. Run with KiCad's Python; inspect/refill and
route the candidate before promotion. Original component-local geometry is kept.
"""
from route_checked import *
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union


def expanded_x(x):
    return x + sum(8 * min(1, max(0, x - edge)) for edge in (54.5, 72.5, 90.5, 108.5, 126.5))


def point(p):
    x, y = router.xy(p)
    return V(expanded_x(x), y + 6)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=HERE/'eswitch-simple.kicad_pcb')
    source=parser.parse_args().source
    target = OUT / 'power-rework.kicad_pcb'
    OUT.mkdir(parents=True, exist_ok=True)
    b = pcbnew.LoadBoard(str(source))
    bounds=b.GetBoardEdgesBoundingBox()
    assert round(pcbnew.ToMM(bounds.GetWidth()))==136 and round(pcbnew.ToMM(bounds.GetHeight()))==104, 'Migration requires the original 136 x 104 mm board'
    retired=[]
    def remove(item):
        b.Remove(item)
        retired.append(item)
    # Expand only the inter-cell corridors, not footprint geometry.
    for fp in b.GetFootprints():
        fp.SetPosition(point(fp.GetPosition()))
    for t in list(b.GetTracks()):
        if t.GetClass() == 'PCB_VIA':
            t.SetPosition(point(t.GetPosition()))
            continue
        ax, ay = router.xy(t.GetStart()); bx, by = router.xy(t.GetEnd())
        fractions = [0., 1.]
        if bx != ax:
            fractions += [(edge - ax) / (bx - ax) for edge in
                          (54.5, 55.5, 72.5, 73.5, 90.5, 91.5, 108.5, 109.5, 126.5, 127.5)
                          if 0 < (edge - ax) / (bx - ax) < 1]
        fractions.sort()
        for lo, hi in zip(fractions, fractions[1:]):
            clone = pcbnew.PCB_TRACK(b)
            clone.SetNet(t.GetNet()); clone.SetLayer(t.GetLayer()); clone.SetWidth(t.GetWidth())
            clone.SetStart(V(expanded_x(ax + lo * (bx - ax)), ay + lo * (by - ay) + 6))
            clone.SetEnd(V(expanded_x(ax + hi * (bx - ax)), ay + hi * (by - ay) + 6))
            b.Add(clone)
        remove(t)
    for z in b.Zones():
        outline = z.Outline()
        contours = [[point(outline.COutline(i).CPoint(j)) for j in range(outline.COutline(i).PointCount())]
                    for i in range(outline.OutlineCount())]
        outline.RemoveAllContours()
        for vertices in contours: z.AddPolygon(pcbnew.VECTOR_VECTOR2I(vertices))
        z.UnFill()
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts or d.GetClass().startswith('PCB_DIMENSION'):
            remove(d)
        elif d.GetClass() == 'PCB_TEXT':
            d.SetPosition(point(d.GetPosition()))
            if d.GetText() in ('+', '-'):
                d.SetText('-' if d.GetText() == '+' else '+')
        elif d.GetClass() == 'PCB_SHAPE':
            d.SetStart(point(d.GetStart())); d.SetEnd(point(d.GetEnd()))
    perimeter=[(0,6),(36,6),(36,0),(176,0),(176,116),(0,116),(0,6)]
    for start,end in zip(perimeter,perimeter[1:]):
        d = pcbnew.PCB_SHAPE(b); d.SetShape(pcbnew.SHAPE_T_SEGMENT)
        d.SetStart(V(*start)); d.SetEnd(V(*end)); d.SetLayer(pcbnew.Edge_Cuts)
        d.SetWidth(pcbnew.FromMM(.05)); b.Add(d)
    def zone(layer, net, vertices, priority=4):
        z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet('/' + net))
        z.SetAssignedPriority(priority); z.SetLocalClearance(pcbnew.FromMM(.2))
        z.SetMinThickness(pcbnew.FromMM(.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(*p) for p in vertices])); b.Add(z)
        return z
    # Replace cell power pours with explicit, roomy corridors. Keep raw trunk.
    for z in list(b.Zones()):
        if z.GetIsRuleArea(): continue
        net = short_name(z)
        if net.startswith(('VS', 'LOAD')) or (net == 'BATT_RAW' and z.GetAssignedPriority() == 3):
            remove(z)
        elif net == 'BATT_RAW' and z.GetAssignedPriority() == 2:
            z.Outline().RemoveAllContours()
            z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(*p) for p in
                [(37,18),(67,18),(67,34),(58,34),(58,46),(65,46),(65,50),(169,50),(169,66),(55,66),(45,50),(45,34),(37,34)]]))
        elif net == 'GND' and z.GetAssignedPriority() == 0:
            z.Outline().RemoveAllContours()
            z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(0,0),V(176,0),V(176,116),V(0,116)]))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    moved_nets=set()
    for n in range(1, 9):
        cx = 72 + 26 * ((n - 1) % 4)
        def xy(dx, y): return (cx-dx, 110-y) if n > 4 else (cx+dx, y+6)
        def cell_zone(layer, net, vertices, priority=4):
            return zone(layer, net, [xy(*p) for p in vertices], priority)
        for ref in (f'R{n}01',f'R{n}02',f'R{n}03',f'R{n}04',f'R{n}05',f'C{n}03'):
            fp=fps[ref]; x,y=router.xy(fp.GetPosition())
            fp.SetPosition(V(x+(5 if n>4 else -5),y))
            moved_nets.update(short_name(p) for p in fp.Pads() if short_name(p)!='GND')
        for t in list(b.GetTracks()):
            if t.GetClass()!='PCB_VIA' or short_name(t)!='GND': continue
            x,y=router.xy(t.GetPosition()); dx=(cx-x if n>4 else x-cx); ly=(110-y if n>4 else y-6)
            if -8<dx<-3 and 29<ly<41: remove(t)
        for pad in fps[f'J{n+10}'].Pads():
            pad.SetNet(b.FindNet('/' + (f'LOAD{n}' if pad.GetNumber() == '1' else 'GND')))
        for layer in (pcbnew.F_Cu, pcbnew.In2_Cu):
            cell_zone(layer, 'BATT_RAW', [(-7.5,29.5),(1.4,29.5),(1.4,39),(-3.3,39),(-3.3,53),(-9.5,53),(-9.5,39),(-7.5,37)], 6+n)
        for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            spreader=[(-14,13),(1.4,13),(1.4,28.8),(-14,28.8)]
            if layer!=pcbnew.F_Cu:
                spreader=[(-10,13),(1.4,13),(1.4,28.8),(-1.4,28.8),(-1.4,21.8),(-10,21.8)]
            cell_zone(layer, f'VS{n}', spreader)
            cell_zone(layer, f'LOAD{n}', [(2,8.2),(11.5,8.2),(11.5,46.5),(-3.3,46.5),(-3.3,39.5),(2,39.5)])
        # Put the TVS beside the connector, with a short VS connection. The old
        # U-shaped front trace enclosed the connector's ground landing.
        tvs=fps[f'D{n}04']
        oldpads=[router.xy(p.GetPosition()) for p in tvs.Pads()]
        tvs.SetPosition(V(*xy(-10,4.6)))
        for t in list(b.GetTracks()):
            tx,ty=router.xy(t.GetPosition())
            if t.GetClass()=='PCB_VIA' and any(abs(tx-x)<.01 and abs(ty-y)<1.3 for x,y in oldpads):
                remove(t)
            elif t.GetClass()=='PCB_TRACK' and short_name(t)==f'VS{n}':
                ends=[router.xy(t.GetStart()),router.xy(t.GetEnd())]
                if all((y<23 if n<=4 else y>93) for x,y in ends): remove(t)
        p=next(p for p in tvs.Pads() if p.GetNumber()=='1')
        t=pcbnew.PCB_TRACK(b);t.SetStart(p.GetPosition());t.SetEnd(V(*xy(-6.6,16)))
        t.SetLayer(pcbnew.B_Cu);t.SetWidth(pcbnew.FromMM(1.5));t.SetNet(p.GetNet());b.Add(t)
        # Replace the four EP vias with a twelve-via array (VS, never ground).
        ux, uy = router.xy(fps[f'U{n}'].GetPosition())
        for t in list(b.GetTracks()):
            if t.GetClass() == 'PCB_VIA' and short_name(t) == f'VS{n}':
                x,y = router.xy(t.GetPosition())
                if abs(x-ux)<1.4 and abs(y-uy)<2: remove(t)
        for dx in (-.8,0,.8):
            for dy in (-1.5,-.5,.5,1.5):
                v=pcbnew.PCB_VIA(b); v.SetPosition(V(ux+dx,uy+dy))
                v.SetWidth(pcbnew.FromMM(.6)); v.SetDrill(pcbnew.FromMM(.3))
                v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); v.SetNet(b.FindNet(f'/VS{n}')); b.Add(v)
    target.with_suffix('.kicad_pro').write_text(source.with_suffix('.kicad_pro').read_text())
    shutil.copyfile(HERE/'fp-lib-table', OUT/'fp-lib-table')
    if not (OUT/'lib').exists(): (OUT/'lib').symlink_to(HERE/'lib', target_is_directory=True)
    # Reopen signals which cross a reserved battery feed, plus signals at the
    # relocated TVS pads. The checked router must respect both battery layers.
    reopen={'ADC_CLAMP_2V5','IS2','IS3','IS8','IN7'} | moved_nets
    for t in list(b.GetTracks()):
        if short_name(t)=='BATT_RAW' and t.GetClass()=='PCB_TRACK' and t.GetLayer()==pcbnew.B_Cu:
            remove(t)
    p=next(p for p in fps['F9'].Pads() if short_name(p)=='BATT_RAW')
    v=pcbnew.PCB_VIA(b);v.SetPosition(V(55,44));v.SetWidth(pcbnew.FromMM(.8));v.SetDrill(pcbnew.FromMM(.4))
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(p.GetNet());b.Add(v)
    t=pcbnew.PCB_TRACK(b);t.SetStart(p.GetPosition());t.SetEnd(v.GetPosition())
    t.SetLayer(pcbnew.B_Cu);t.SetWidth(pcbnew.FromMM(1));t.SetNet(p.GetNet());b.Add(t)
    for z in b.Zones():
        if not z.GetIsRuleArea() and short_name(z)=='BATT_RAW':
            z.SetZoneName('protected_power_battery')
    # Explicit ground highways, reserved by the signal router as well as poured.
    for layer in (pcbnew.F_Cu,pcbnew.B_Cu):
        highway=unary_union([Polygon(vertices) for vertices in
                            [[(36,0),(176,0),(176,6),(36,6)],
                             [(36,110),(176,110),(176,116),(36,116)],
                             [(166,0),(176,0),(176,116),(166,116)],
                             [(37,76),(43,76),(43,116),(37,116)]]])
        z=zone(layer,'GND',list(highway.exterior.coords)[:-1],1)
        z.SetZoneName('protected_power_return')
    raw={layer:unary_union([Polygon([router.xy(z.Outline().COutline(0).CPoint(j))
                                   for j in range(z.Outline().COutline(0).PointCount())])
                           for z in b.Zones() if not z.GetIsRuleArea() and short_name(z)=='BATT_RAW' and z.GetLayer()==layer])
         for layer in (pcbnew.F_Cu,pcbnew.In2_Cu)}
    for t in b.GetTracks():
        net=short_name(t)
        if t.GetClass()!='PCB_TRACK' or t.GetLayer() not in raw: continue
        if net.startswith(('IN','DEN','IS','UGND','LEDK')) and LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).intersects(raw[t.GetLayer()]):
            reopen.add(net)
    for t in list(b.GetTracks()):
        if short_name(t) in reopen: remove(t)
    print('Signals reopened:',sorted(reopen),flush=True)
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.GetLayer()==pcbnew.In2_Cu:
            z.SetMinThickness(pcbnew.FromMM(.3))
    result = check(b, target)
    original=b
    b = pcbnew.LoadBoard(str(target))
    fps={f.GetReference():f for f in b.GetFootprints()}
    router.W, router.H = 176.,116.
    router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
    router.SIZE=router.NX*router.NY
    ground_stitch(b,result)
    gnd=b.FindNet('/GND')
    _,blocked=router.obstacles(AliasBoard(b),gnd.GetNetCode(),.25,.8)
    existing=[router.xy(t.GetPosition()) for t in b.GetTracks() if t.GetClass()=='PCB_VIA']
    sites=[(x,y) for x in range(54,175,3) for y in (3,113)]
    sites += [(173,y) for y in range(6,113,3)]
    # Terminal landing stitching and the return-stud fanout.
    for n in range(1,9):
        p=next(p for p in fps[f'J{n+10}'].Pads() if short_name(p)=='GND')
        x,y=router.xy(p.GetPosition())
        sites += [(x+dx,y+dy) for dx in (-2,0,2) for dy in (-2,2)]
    sites += [(x,y) for x in range(38,53,2) for y in range(76,96,2)]
    for x,y in sites:
        if blocked[round(y/router.STEP)*router.NX+round(x/router.STEP)]: continue
        if any(math.hypot(x-a,y-b)<1 for a,b in existing): continue
        v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(pcbnew.FromMM(.8));v.SetDrill(pcbnew.FromMM(.4))
        v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(gnd);b.Add(v);existing.append((x,y))
    result=check(b,target)
    target.with_suffix('.summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Candidate:', target, 'violations:', len(result['violations']), 'gaps:', len(result['unconnected_items']))


if __name__ == '__main__': main()
