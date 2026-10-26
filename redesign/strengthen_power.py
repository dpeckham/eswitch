#!/usr/bin/env python3
"""Protect terminal return landings and remove feed-junction obstructions."""
from power_geometry import *


def main():
    p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.board));retired=[]
    def remove(item): b.Remove(item);retired.append(item)
    # D3 is on B.Cu. Connect its VIN landing on that layer rather than cutting
    # the shared battery feed with a front-side TVS spreader and diagonal track.
    for z in b.Zones():
        if not z.GetIsRuleArea() and short_name(z)=='VIN' and z.GetLayer()==pcbnew.F_Cu and z.GetAssignedPriority()==6:
            z.SetLayer(pcbnew.B_Cu)
    for t in list(b.GetTracks()):
        x,y=router.xy(t.GetPosition())
        if t.GetClass()=='PCB_VIA':
            if short_name(t)=='VIN' and abs(x-53.4)<.01 and 55<=y<=59: remove(t)
            elif short_name(t)=='GND' and any(math.hypot(x-u,y-v)<.01 for u,v in [(67.2,43.8),(92.6,43.8),(119.2,43.8),(145.2,43.8)]): remove(t)
        elif short_name(t)=='VIN' and t.GetLayer()==pcbnew.F_Cu:
            ends=[router.xy(t.GetStart()),router.xy(t.GetEnd())]
            if any(abs(u-53.4)<.01 and abs(v-57)<.01 for u,v in ends): t.SetLayer(pcbnew.B_Cu)
    fps={f.GetReference():f for f in b.GetFootprints()};reserved=[]
    for n in range(1,9):
        cx=72+26*((n-1)%4)
        def xy(dx,y):return (cx-dx,110-y) if n>4 else (cx+dx,y+6)
        pad=next(p for p in fps[f'J{n+10}'].Pads() if short_name(p)=='GND')
        path=[router.xy(pad.GetPosition()),xy(-2.8,7),xy(-2.8,-3)]
        shape=LineString(path).buffer(1.65,resolution=8,join_style=2)
        reserved.append(shape)
        for layer in (pcbnew.F_Cu,pcbnew.B_Cu):
            z=pcbnew.ZONE(b);z.SetLayer(layer);z.SetNet(pad.GetNet());z.SetAssignedPriority(3)
            z.SetZoneName('protected_power_terminal_return');z.SetLocalClearance(pcbnew.FromMM(.2))
            z.SetMinThickness(pcbnew.FromMM(.3));z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
            z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(*point) for point in list(shape.exterior.coords)[:-1]]));b.Add(z)
    reserved=unary_union(reserved)
    removed={}
    for t in list(b.GetTracks()):
        net=short_name(t)
        if net=='GND': continue
        via=t.GetClass()=='PCB_VIA'
        shape=Point(router.xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2+.2) if via else LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2+.2)
        if (via or t.GetLayer() in (pcbnew.F_Cu,pcbnew.B_Cu)) and shape.intersects(reserved):
            assert not net.startswith(('VS','LOAD','VIN','BATT')), ('Power collision in terminal return',net)
            removed[net]=removed.get(net,0)+1;remove(t)
    a.output.with_suffix('.kicad_pro').write_text(a.board.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    objects=items_by_id(b)
    for violation in report['violations']:
        if violation['type']=='tracks_crossing':
            items=[objects[i['uuid']] for i in violation['items']]
            if any(short_name(item)=='VIN' for item in items):
                for item in items:
                    if short_name(item)!='VIN':remove(item)
    report=check(b,a.output)
    a.output.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Local signal segments reopened:',removed,'violations:',report['violations'],'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
