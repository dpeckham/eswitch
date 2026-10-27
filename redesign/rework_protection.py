#!/usr/bin/env python3
"""Migrate PWR2 to a 212x116 protection candidate; never promote automatically."""
from route_checked import *
from pcb_nets import sync_metadata
from gen_pcb import read_netlist
import circuit


def main():
    source = HERE / 'eswitch-simple.kicad_pcb'
    target = OUT / 'protection-placed.kicad_pcb'
    b = pcbnew.LoadBoard(str(source))
    assert round(pcbnew.ToMM(b.GetBoardEdgesBoundingBox().GetWidth())) == 176
    retired = []
    def remove(item):
        b.Remove(item)
        retired.append(item)
    # Translate the old layout intact before replacing power connectivity.
    delta = V(36, 0)
    for fp in b.GetFootprints(): fp.Move(delta)
    for t in b.GetTracks(): t.Move(delta)
    for z in b.Zones(): z.Move(delta)
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts or d.GetClass().startswith('PCB_DIMENSION'):
            remove(d)
        else:
            d.Move(delta)
            if d.GetClass()=='PCB_TEXT' and 'PWR2:' in d.GetText():
                d.SetText(d.GetText().replace('PWR2:', 'PWR3:'))
                d.SetPosition(V(66,113))
    perimeter = [(0,6),(72,6),(72,0),(212,0),(212,116),(0,116),(0,6)]
    for a,c in zip(perimeter, perimeter[1:]):
        d=pcbnew.PCB_SHAPE(b); d.SetShape(pcbnew.SHAPE_T_SEGMENT)
        d.SetLayer(pcbnew.Edge_Cuts); d.SetWidth(pcbnew.FromMM(.05))
        d.SetStart(V(*a)); d.SetEnd(V(*c)); b.Add(d)
    parts={p.ref:p for p in circuit.build() if not p.ref.startswith('#')}
    for fp in list(b.GetFootprints()):
        if fp.GetReference() not in parts: remove(fp)
        elif fp.GetReference() in {f'F{n}' for n in range(1,9)}:
            for graphic in fp.GraphicalItems():
                if graphic.GetClass()=='PCB_TEXT' and graphic.GetText() in ('SW','COM','LOAD'):
                    graphic.SetText({'SW':'AUTO','COM':'LOAD','LOAD':'RAW'}[graphic.GetText()])
    # Remove power copper whose old function is no longer valid. Keep existing
    # logic/signal routing and ground structures; refill will expose conflicts.
    for t in list(b.GetTracks()):
        net=short_name(t)
        if net=='BATT_RAW' or net.startswith(('VS','LOAD')):
            remove(t)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea() and (short_name(z)=='BATT_RAW' or short_name(z).startswith(('VS','LOAD'))): remove(z)
    comps,nets=read_netlist(str(OUT/'protection.net'))
    for name in nets:
        if not b.FindNet(name): b.Add(pcbnew.NETINFO_ITEM(b,name))
    net_by_pin={(ref,pin):name for name,pins in nets.items() for ref,pin in pins}
    placements={
        'F10':(12,62,-90,False),
        'Q6':(30,35,0,False),'Q7':(30,51,0,False),
        'Q8':(30,67,0,False),'Q9':(30,83,0,False),
        'Q10':(28,100,0,False),'Q11':(50,108,0,False),
        'U15':(21,20,0,True),
        'R20':(33,30,0,True),'R21':(33,46,0,True),
        'R22':(33,62,0,True),'R23':(33,78,0,True),
        'R24':(28,108,0,False),'R25':(58,108,0,False),
        'R26':(4,9,0,False),
        'R27':(6,28,0,True),'R28':(6,32,0,True),'R29':(6,36,0,True),
        'D6':(30,15,90,False),'D7':(30,24,90,False),
        'D8':(13,30,90,True),'D9':(20,33,90,True),
        'D10':(53,99,90,True),
        'C25':(30,15,0,True),'C26':(20,26,0,True),
        'C27':(25,20,90,True),'C28':(28,27,0,True),'C29':(43,94,0,True)}
    fps={f.GetReference():f for f in b.GetFootprints()}
    fps['H1'].SetPosition(V(34,112))
    stock=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
    for ref,part in parts.items():
        if ref not in fps:
            lib,name=part.footprint.split(':')
            folder=HERE/'lib/eswitch.pretty' if lib=='eswitch' else stock/(lib+'.pretty')
            fp=pcbnew.FootprintLoad(str(folder),name)
            assert fp is not None,(ref,part.footprint)
            fp.SetReference(ref); b.Add(fp); fps[ref]=fp
            x,y,angle,back=placements[ref]
            fp.SetPosition(V(x,y))
            if back: fp.Flip(fp.GetPosition(),False)
            fp.SetOrientationDegrees(angle)
            fp.Reference().SetVisible(False)
            fp.Value().SetVisible(False)
        for pad in fps[ref].Pads():
            name=net_by_pin.get((ref,pad.GetNumber()))
            pad.SetNet(b.FindNet(name) if name and not name.startswith('unconnected-') else b.FindNet(0))
    sync_metadata(b,OUT/'protection.net')
    # Extend the base ground planes into the new strip.
    for z in b.Zones():
        if not z.GetIsRuleArea() and short_name(z)=='GND' and z.GetAssignedPriority()==0:
            z.Outline().RemoveAllContours()
            z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(0,0),V(212,0),V(212,116),V(0,116)]))
    sequence=[0]
    def zone(layer,net,vertices,priority=4):
        sequence[0]+=1
        z=pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet('/'+net))
        z.SetAssignedPriority(priority*100+sequence[0]); z.SetLocalClearance(pcbnew.FromMM(.25))
        z.SetMinThickness(pcbnew.FromMM(.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(*p) for p in vertices])); b.Add(z)
        z.SetZoneName('protected_power_'+net)
        return z
    # Separate distribution planes: raw BYPASS on the front; protected AUTO on
    # In2 and local rear spreaders. Neither bus is a movable fuse's common pin.
    zone(pcbnew.F_Cu,'BATT_RAW',[(74,18),(91,18),(91,46),(205,46),(205,70),(91,70),(80,43),(74,34)])
    zone(pcbnew.F_Cu,'BATT_RAW',[(5,12),(19,12),(19,23),(89,23),(89,31),(5,31)])
    zone(pcbnew.In2_Cu,'AUTO_PROTECTED',[(27,94),(53,94),(53,51),(205,51),(205,65),(65,65),(65,107),(27,107)])
    # High-voltage drains occupy the right side of the new MOSFET bank. The
    # common-source rail runs along the lead side, isolated from the raw bus.
    zone(pcbnew.F_Cu,'AUTO_FUSED',[(26,28),(40,28),(40,97),(19,112),(5,112),(5,99),(26,86)])
    zone(pcbnew.In2_Cu,'AUTO_FUSED',[(26,28),(40,28),(40,89),(19,112),(5,112),(5,99),(26,86)])
    zone(pcbnew.F_Cu,'PROTECTION_COMMON_SOURCE',[(23,33),(26,33),(26,90),(47,90),(47,101),(23,101)])
    for n in range(1,9):
        cx=108+26*((n-1)%4)
        def xy(x,y): return (cx-x,116-y) if n>4 else (cx+x,y)
        def cell(layer,net,vertices,priority=5):
            return zone(layer,net,[xy(x,y) for x,y in vertices],priority)
        cell(pcbnew.F_Cu,'BATT_RAW',[(-3,45),(3,45),(3,59),(-3,59)])
        cell(pcbnew.In2_Cu,'AUTO_PROTECTED',[(-12,19),(1.4,19),(1.4,34),(-3,34),(-3,59),(-12,59)])
        cell(pcbnew.B_Cu,'AUTO_PROTECTED',[(-12,19),(1.4,19),(1.4,34),(-12,34)])
        cell(pcbnew.F_Cu,'AUTO_PROTECTED',[(-1.4,29),(1.4,29),(1.4,34),(-1.4,34)])
        cell(pcbnew.B_Cu,f'PROFET_OUT{n}',[(-3,22),(9,22),(9,35),(2,35),(2,29),(-3,29)],10)
        cell(pcbnew.F_Cu,f'LOAD{n}',[(2,10),(10,10),(10,41),(-3,41),(-3,35),(4.5,35),(4.5,18),(2,18)],10)
        ux,uy=router.xy(fps[f'U{n}'].GetPosition())
        for dx in (-.8,0,.8):
            for dy in (-1.5,-.5,.5,1.5):
                v=pcbnew.PCB_VIA(b);v.SetPosition(V(ux+dx,uy+dy));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
                v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(b.FindNet('/AUTO_PROTECTED'));b.Add(v)
    target.with_suffix('.kicad_pro').write_text(source.with_suffix('.kicad_pro').read_text())
    # Recover accepted channel-local routing from the earlier placement pass.
    # The changed input-stage mechanics are left for a fresh route/check pass.
    routed=OUT/'protection-signals2.kicad_pcb'
    if routed.exists():
        old=pcbnew.LoadBoard(str(routed))
        def signature(t):
            if t.GetClass()=='PCB_VIA': return (short_name(t),'via',tuple(router.xy(t.GetPosition())))
            return (short_name(t),t.GetLayer(),tuple(sorted((tuple(router.xy(t.GetStart())),tuple(router.xy(t.GetEnd()))))))
        existing={signature(t) for t in b.GetTracks()}
        for t in old.GetTracks():
            positions=[router.xy(t.GetPosition())] if t.GetClass()=='PCB_VIA' else [router.xy(t.GetStart()),router.xy(t.GetEnd())]
            key=signature(t)
            if min(p[0] for p in positions)<90 or key in existing: continue
            net=b.FindNet(t.GetNetname())
            if not net: continue
            if t.GetClass()=='PCB_VIA':
                clone=pcbnew.PCB_VIA(b);clone.SetPosition(t.GetPosition());clone.SetWidth(t.GetWidth());clone.SetDrill(t.GetDrillValue())
                clone.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
            else:
                clone=pcbnew.PCB_TRACK(b);clone.SetStart(t.GetStart());clone.SetEnd(t.GetEnd());clone.SetWidth(t.GetWidth());clone.SetLayer(t.GetLayer())
            clone.SetNet(net);b.Add(clone);existing.add(key)
    report=check(b,target)
    print(target)
    print('Violations:',len(report['violations']),'unconnected:',len(report['unconnected_items']))


if __name__=='__main__': main()
