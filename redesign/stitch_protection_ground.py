#!/usr/bin/env python3
"""Stitch detached outer ground islands to the existing inner ground plane."""
from power_geometry import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals9.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-ground.kicad_pcb')
    p.add_argument('--route-islands',action='store_true',help='Route isolated logic ground pads to existing grounded vias when direct stitching is blocked')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));retired=[]
    if a.route_islands:router.STEP=.05;router.GUARD=.005
    bounds=b.GetBoardEdgesBoundingBox()
    router.W,router.H=round(pcbnew.ToMM(bounds.GetWidth())),round(pcbnew.ToMM(bounds.GetHeight()))
    router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
    router.SIZE=router.NX*router.NY
    gnd=b.FindNet('/GND')
    _,blocked=router.obstacles(AliasBoard(b,power_pad_escapes=True,ground_power_escapes=True),gnd.GetNetCode(),.25,.5)
    anchor=next(f for f in b.GetFootprints() if f.GetReference()=='J3')
    center=Point(router.xy(anchor.GetPosition()))
    plane=next(p for p in components(copper(b,'GND',pcbnew.In1_Cu)) if p.covers(center))
    through=[router.xy(t.GetPosition()) for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and short_name(t)=='GND']
    through.extend(router.xy(p.GetPosition()) for f in b.GetFootprints() for p in f.Pads()
                   if short_name(p)=='GND' and p.GetDrillSize().x)
    through=[pt for pt in through if plane.covers(Point(pt))]
    added=[];unresolved=[];removed=[];routed=0
    for layer in (pcbnew.F_Cu,pcbnew.B_Cu):
        for shape in components(copper(b,'GND',layer)):
            if shape.is_empty or shape.area<.001 or any(shape.buffer(.002).covers(Point(pt)) for pt in through):continue
            touches_pad=any(short_name(p)=='GND' and p.IsOnLayer(layer)
                            and shape.buffer(.002).covers(Point(router.xy(p.GetPosition())))
                            for f in b.GetFootprints() for p in f.Pads())
            touches_via=any(t.GetClass()=='PCB_VIA' and short_name(t)=='GND'
                            and shape.buffer(.002).covers(Point(router.xy(t.GetPosition()))) for t in b.GetTracks())
            if not touches_pad and not touches_via:
                # Leftover ground-track fragments can keep otherwise empty
                # pour islands alive after their original via was displaced.
                for t in list(b.GetTracks()):
                    if t.GetClass()=='PCB_TRACK' and short_name(t)=='GND' and t.GetLayer()==layer and shape.buffer(.002).covers(Point(router.xy(t.GetStart()))):
                        removed.append(t.m_Uuid.AsString());b.Remove(t);retired.append(t)
                continue
            xmin,ymin,xmax,ymax=shape.bounds
            center=shape.representative_point()
            candidates=[(i*.1,j*.1) for i in range(math.ceil(xmin/.1),math.floor(xmax/.1)+1)
                        for j in range(math.ceil(ymin/.1),math.floor(ymax/.1)+1)]
            candidates.sort(key=lambda pt:(pt[0]-center.x)**2+(pt[1]-center.y)**2)
            for x,y in candidates:
                pt=Point(x,y)
                if not shape.covers(pt) or not plane.covers(pt):continue
                col,row=round(x/router.STEP),round(y/router.STEP)
                if not(0<=col<router.NX and 0<=row<router.NY) or blocked[row*router.NX+col]:continue
                if any(math.hypot(x-u,y-v)<.9 for u,v in through):continue
                via=pcbnew.PCB_VIA(b);via.SetPosition(V(x,y));via.SetWidth(pcbnew.FromMM(.5));via.SetDrill(pcbnew.FromMM(.3))
                via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);via.SetNet(gnd);b.Add(via)
                through.append((x,y));added.append((x,y));break
            else:
                connected=False
                if a.route_islands and touches_pad:
                    blocked_tracks,blocked_vias=router.obstacles(AliasBoard(b,ground_power_escapes=True),gnd.GetNetCode(),.2,.6)
                    source_items=[p for f in b.GetFootprints() for p in f.Pads() if short_name(p)=='GND'
                                  and p.IsOnLayer(layer) and shape.buffer(.002).covers(Point(router.xy(p.GetPosition())))]
                    target_items=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and short_name(t)=='GND'
                                  and plane.covers(Point(router.xy(t.GetPosition()))) and not shape.covers(Point(router.xy(t.GetPosition())))]
                    starts=router.anchors(source_items,blocked_tracks);goals=router.anchors(target_items,blocked_tracks)
                    if starts and goals and not(starts.keys()&goals.keys()):
                        path=router.search(blocked_tracks,blocked_vias,starts,goals)
                        if path:
                            router.add_route(b,gnd,path,starts,goals,.2,.6,.3)
                            b.BuildConnectivity();routed+=1;connected=True
                if not connected:unresolved.append(dict(layer=b.GetLayerName(layer),bounds=list(shape.bounds),area=shape.area))
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    report=check(b,a.output)
    a.output.with_suffix('.stitch.json').write_text(json.dumps(dict(added=added,routed_islands=routed,removed_orphan_tracks=removed,unresolved=unresolved),indent=2)+'\n')
    print('Added ground vias:',len(added),'unresolved islands:',len(unresolved),
          'copper errors:',len(errors(report)),'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
