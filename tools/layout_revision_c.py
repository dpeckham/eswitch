#!/usr/bin/env python3
"""One-time migration from a saved revision B board; retain checked logic routing.

Usage: kicad python3.11 tools/layout_revision_c.py path/to/revision-b.kicad_pcb
The saved board, subsequently routed and reviewed, is the fabrication authority.
"""
import math
import sys
from pathlib import Path
import pcbnew
import design
import revision_c as rev
from gen_pcb import Board, V, NETLIST, OUT_PCB, apply_rules, persist_project_rules
from pcb_nets import sync_metadata, short_name
from pcb_io import save_board, fill_zones
from fabrication_rules import configure_usb

F,B,I1,I2 = pcbnew.F_Cu,pcbnew.B_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu


class Shifted:
    """Retain the reviewed PROFET support layout below the new breaker bank."""
    def __init__(self, bd):
        self.bd,self.fps = bd,bd.fps
    def place(self,ref,x,y,rot=0,side='B'):
        return self.bd.place(ref,x,y+90.5,rot,side)
    def pad_pos(self,ref,pin):
        x,y=self.bd.pad_pos(ref,pin)
        return x,y-90.5
    def pin_up(self,*args): self.bd.pin_up(*args)
    def track(self,layer,net,pts,width):
        self.bd.track(layer,net,[(x,y+90.5) for x,y in pts],width)
    def via(self,net,x,y,*args): self.bd.via(net,x,y+90.5,*args)
    def zone(self,layer,net,pts,**kw):
        return self.bd.zone(layer,net,[(x,y+90.5) for x,y in pts],**kw)
    def rect_zone(self,layer,net,x1,y1,x2,y2,**kw):
        return self.bd.rect_zone(layer,net,x1,y1+90.5,x2,y2+90.5,**kw)
    def text(self,s,x,y,**kw): self.bd.text(s,x,y+90.5,**kw)


def keepout(bd,x,y,r=4):
    for layer in (F,B,I1,I2):
        z=pcbnew.ZONE(bd.b)
        z.SetLayer(layer); z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowZoneFills(True)
        # Circumscribed polygon guarantees >=4mm copper clearance everywhere.
        rr=r/math.cos(math.pi/48)
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([
            V(x+rr*math.cos(i*math.pi/24),y+rr*math.sin(i*math.pi/24)) for i in range(48)]))
        z.SetZoneName(f'M3_hardware_{x}_{y}')
        bd.b.Add(z)


def branch(bd,n):
    x=rev.CX[n-1]
    sense,feed=f'BR_SENSE{n}',f'CHFEED{n}'
    count=rev.SHUNT_COUNT[n]
    # Vertical chain, pin 1 upstream. Sense pickup uses pad centres, never
    # the power-plane via field; the two Kelvin routes run together to U21-28.
    for k in range(count):
        ref=f'R{n}2{k}'
        y=61.5-(count-1-k)*8.5
        bd.place(ref,x+2,y,90,'B'); bd.pin_up(ref)
        a=bd.pad_pos(ref,'1'); b=bd.pad_pos(ref,'2')
        if k==0:
            for layer in (F,I2,B):
                bd.rect_zone(layer,'+12V',x-.1,30,x+4.1,a[1]+1,priority=4)
            for xx in (x+.6,x+2,x+3.4):
                for yy in (a[1]-3.5,a[1]-2.2): bd.via('+12V',xx,yy,.8,.4)
        if k<count-1:
            nxt=(x+2,y+8.5-2.16)
            bd.track(B,f'BR_R{n}_{k+1}',[b,nxt],3.4)
    q=f'Q{10+n}'
    bd.place(q,x+2,76.5,90,'B')
    if bd.pad_pos(q,'2')[1]<bd.pad_pos(q,'5')[1]:
        bd.fps[q].SetOrientationDegrees(bd.fps[q].GetOrientationDegrees()+180)
    bd.rect_zone(B,sense,x-2.5,63,x+6.5,78.5,priority=4)
    bd.rect_zone(F,sense,x-2.5,64,x+6.5,78.5,priority=4)
    for xx in (x-1.7,x-.5,x+4.5,x+5.7):
        for yy in (68,69.5,71,72.5): bd.via(sense,xx,yy,.8,.4)
    for layer in (F,B):
        bd.rect_zone(layer,feed,x-2.5,80,x+7,114,priority=2)
    for xx in (x-.8,x+.6,x+2,x+3.4):
        for yy in (82,83.4,84.8): bd.via(feed,xx,yy,.8,.4)
    for yy in (87,91,95,99,103): bd.via(feed,x+6,yy,.8,.4)
    bd.place(f'U{20+n}',x-7.5,62.5,0,'B')
    # External clamp lives beside, clear of the fuse's through-hole pins.
    bd.place(f'D{n}11',x-8.5,86,90,'B')
    cath=bd.pad_pos(f'D{n}11','2')
    bd.track(B,feed,[cath,(x-2.2,cath[1]),(x-2.2,84)],2.5)
    for ref,y,rot in [(f'C{n}11',47,0),(f'C{n}12',51,0),
                       (f'C{n}13',55,0),
                       (f'R{n}12',36,0),(f'R{n}13',39,0),
                       (f'R{n}14',42,0),(f'R{n}15',32,0)]:
        bd.place(ref,x-7.5,y,rot,'B')
    bd.place(f'SW{n+2}',x+1,86.5,0,'F')
    bd.text(f'RESET CH{n}',x+1,91.6,size=.8)
    bd.place(f'D{n}03',x+8.5,113.9,0,'B')
    bd.place(f'TP{16+n}',x-8,94.2,0,'B')
    bd.place(f'R{n}11',x+9,65.5,0,'B')
    bd.place(f'Q{30+n}',x+9,70,0,'B')
    bd.place(f'R{n}16',x+9,74.5,0,'B')
    bd.place(f'R{n}17',x-7.5,68.5,0,'B')
    bd.place(f'D{n}12',x-7.5,72,0,'B')
    # Distributed common-bus reservoir, on the accessible top face.
    for k,(xx,yy) in enumerate(((x-6,16),(x+6,16),(x,29))):
        bd.place(f'C{n}{14+k}',xx,yy,90,'F')
        for pin in ('1','2'):
            px,py=bd.pad_pos(f'C{n}{14+k}',pin)
            net='+12V' if pin=='1' else 'GND'
            for dx in (-.65,.65):
                for dy in (-.65,.65):
                    point=V(px+dx,py+dy)
                    if any(t.GetClass()=='PCB_VIA' and (t.GetPosition()-point).EuclideanNorm()<pcbnew.FromMM(.66)
                           for t in bd.b.GetTracks()): continue
                    bd.via(net,px+dx,py+dy,.8,.4)
    # Dedicated shunt sense pair: short, adjacent, on F.Cu with local escapes.
    # Pin coordinates depend on flipped footprint; route pair after placement
    # with a local router, keeping the power path fixed.
    bd.text(f'CH{n} LATCH',x,57,layer=pcbnew.F_SilkS,size=1.0)


def preserve_channel(bd,old,n,refs):
    """Carry forward the native, DRC-clean local channel routes and placements."""
    import re
    center=old.FindFootprintByReference(f'U{n}').GetPosition()
    ox,oy=pcbnew.ToMM(center.x),pcbnew.ToMM(center.y)
    delta=V(rev.CX[n-1]-ox,125.5-oy)
    aliases={short_name(net):net for net in bd.b.GetNetsByName().values()}
    for ref in refs:
        fp=old.FindFootprintByReference(ref)
        if fp is None: continue
        bd.b.Remove(bd.fps[ref])
        new=pcbnew.Cast_to_FOOTPRINT(fp.Duplicate(False));new.Move(delta)
        bd.b.Add(new);bd.fps[ref]=new
        for pad in new.Pads():
            net=bd.pad_net.get((ref,pad.GetNumber()))
            pad.SetNet(aliases[net] if net else bd.b.FindNet(0))
    # Remove the generator's local routes; import the reviewed native ones.
    for track in list(bd.b.GetTracks()):
        if all(abs(pcbnew.ToMM(pt.x)-rev.CX[n-1])<11 and pcbnew.ToMM(pt.y)>93
               for pt in (track.GetStart(),track.GetEnd())):
            bd.b.Remove(track)
    for track in old.GetTracks():
        name=short_name(track)
        if name!='GND' and not re.fullmatch(r'[A-Z_]+0*'+str(n),name): continue
        if not all(abs(pcbnew.ToMM(pt.x)-ox)<9.5 and pcbnew.ToMM(pt.y)>2.5
                   for pt in (track.GetStart(),track.GetEnd())): continue
        new=getattr(pcbnew,'Cast_to_'+track.GetClass())(track.Duplicate())
        new.Move(delta);new.SetNet(aliases[name]);new.SetLocked(False);bd.b.Add(new)
    for zone in list(bd.b.Zones()):
        if short_name(zone) in (f'VS{n}',f'LOAD{n}'):bd.b.Remove(zone)
    for zone in old.Zones():
        if short_name(zone) not in (f'VS{n}',f'LOAD{n}'):continue
        new=pcbnew.Cast_to_ZONE(zone.Duplicate(False));new.Move(delta)
        new.SetNet(aliases[short_name(zone)]);bd.b.Add(new)


def migrate(source):
    old=pcbnew.LoadBoard(str(source))
    bd=Board(); b=bd.b
    design.build()
    aliases={short_name(net):net for net in bd.nets.values()}
    chrefs={f'{prefix}{n}{suffix}' for n in range(1,9)
            for prefix,suffix in [('R','01'),('R','02'),('R','03'),('R','04'),('R','05'),
                                 ('R','06'),('R','07'),('R','08'),('C','01'),('C','02'),
                                 ('C','03'),('C','04'),('D','01'),('D','02')]}
    chrefs.update(design.OUTPUT_REFS)
    chrefs.update(f'{prefix}{n}' for prefix in ('F','U') for n in range(1,9))
    for fp in old.GetFootprints():
        ref=fp.GetReference()
        if ref in chrefs or ref.startswith('H'): continue
        new=pcbnew.Cast_to_FOOTPRINT(fp.Duplicate(False)); b.Add(new); bd.fps[ref]=new
        for pad in new.Pads():
            net=bd.pad_net.get((ref,pad.GetNumber()))
            pad.SetNet(aliases[net] if net else b.FindNet(0))
    for t in old.GetTracks():
        net=short_name(t)
        if net not in aliases: continue
        if max(t.GetStart().x,t.GetEnd().x)>pcbnew.FromMM(121.5): continue
        if net in ('IN1','HS_VCC','HS_SENSE','DGATE_MAIN'): continue
        if net in ('RXD0','TXD0'): continue
        if net.startswith(('IS','IN')) and max(t.GetStart().x,t.GetEnd().x)>pcbnew.FromMM(30): continue
        new=getattr(pcbnew, "Cast_to_"+t.GetClass())(t.Duplicate()); b.Add(new); new.SetNet(aliases[net]); new.SetLocked(False)
    # Retain local input/USB/buck zones. Rebuild planes and all channel copper.
    for z in old.Zones():
        if z.GetZoneName().startswith('usb_reference_'): continue
        if z.GetIsRuleArea():
            if 'antenna' in z.GetZoneName().lower() or z.GetBoundingBox().GetBottom()<pcbnew.FromMM(2):
                b.Add(z.Duplicate(False))
            continue
        if short_name(z)=='GND': continue
        box=z.GetBoundingBox()
        if box.GetRight()>pcbnew.FromMM(122): continue
        if short_name(z) not in aliases: continue
        new=pcbnew.Cast_to_ZONE(z.Duplicate(False)); b.Add(new); new.SetNet(aliases[short_name(z)])
    for drawing in old.GetDrawings():
        if drawing.GetLayer()==pcbnew.Edge_Cuts: continue
        box=drawing.GetBoundingBox()
        if box.GetRight()<pcbnew.FromMM(121):
            if drawing.GetClass()=='PCB_TEXT' and ('REV' in drawing.GetText() or 'FAULT:' in drawing.GetText()): continue
            b.Add(drawing.Duplicate())
    # Move connector and its immediate escape copper together; stretch only
    # segments that cross the escape boundary, preserving the long USB pair.
    bd.fps['J4'].Move(V(-1.325,0))
    for pad in bd.fps['J4'].Pads():
        if pad.GetNumber() in ('A1','A12','B1','B12'):
            pad.SetSize(V(.6,1.11))
    for ref in ('J4','U10'):
        for pad in bd.fps[ref].Pads():
            if pad.GetAttribute()==pcbnew.PAD_ATTRIB_PTH:
                s,d=pad.GetSize(),pad.GetDrillSize()
                pad.SetSize(pcbnew.VECTOR2I(max(s.x,d.x+pcbnew.FromMM(.52)),max(s.y,d.y+pcbnew.FromMM(.52))))
    for t in b.GetTracks():
        if t.GetClass()!='PCB_TRACK': continue
        if short_name(t) not in ('USB_D+','USB_D-','VBUS','GND','CC1','CC2'): continue
        for getter,setter in ((t.GetStart,t.SetStart),(t.GetEnd,t.SetEnd)):
            pt=getter()
            if pt.x<pcbnew.FromMM(9.1) and pcbnew.FromMM(45)<pt.y<pcbnew.FromMM(58):
                setter(pt+V(-1.325,0))
        if short_name(t)=='VBUS' and abs(t.GetLength()-pcbnew.FromMM(1.34164))<100:
            t.SetWidth(pcbnew.FromMM(.28))
    # Gate route now uses an inner layer, restoring continuous B.Cu sources.
    for ref in ('Q1','Q2'):
        x,y=bd.pad_pos(ref,'4')
        bd.track(B,'DGATE_MAIN',[(x,y),(x-.65,y)],.2)
        bd.via('DGATE_MAIN',x-.65,y,.55,.3)
        bd.track(I2,'DGATE_MAIN',[(x-.65,y),(51.8,y),(51.8,28)],.2)
    bd.via('DGATE_MAIN',51.8,28,.6,.3)
    bd.track(B,'DGATE_MAIN',[(51.8,28),(51.8,33.85),(60.5,33.85),
                              (61.3,33.05),bd.pad_pos('U12','1')],.2)
    for y0 in (10,23):
        for x in (48.6,49.8,51.0):
            for dy in (-1.2,0,1.2,2.4):
                if x==48.6 and ((y0==10 and dy==2.4) or (y0==23 and dy==-1.2)): continue
                bd.via('BATT_RAW',x,y0+dy,.8,.4)
    # Main Kelvin pair on F.Cu, converging just beyond dedicated sense pads.
    for net,pin,dx in [('HS_VCC','3',0),('HS_SENSE','4',.45)]:
        x,y=bd.pad_pos('R20',pin)
        bd.track(B,net,[(x,y),(x,y+2)],.2); bd.via(net,x,y+2,.55,.3)
        lastx=76.1 if dx==0 else 77.85
        bd.track(F,net,[(x,y+2),(x,24+dx),(77+dx,24+dx),
                       (77+dx,30),(lastx,30.4),(lastx,32)],.2)
        bd.via(net,lastx,32,.55,.3)
        # U14 short escapes can be routed with the remaining signals.
    import layout_revision_b as prior
    prior.CX=rev.CX
    for n in range(1,9):
        prior.channel(Shifted(bd),n)
        localrefs={ref for ref in chrefs if ref in (f'F{n}',f'U{n}',design.OUTPUT_REFS[n-1])
                   or (len(ref)==4 and ref[1]==str(n))}
        preserve_channel(bd,old,n,localrefs)
        x=rev.CX[n-1]
        # Eight in-pad thermal vias; front spreader now carries the pad current.
        for xx in (-.65,.65):
            for yy in (-1.35,-.45,.45,1.35):
                point=V(x+xx,125.5+yy)
                blocked=any(t.GetClass()=='PCB_TRACK' and short_name(t)!=f'VS{n}'
                            and pcbnew.SEG(t.GetStart(),t.GetEnd()).Distance(point)<pcbnew.FromMM(.52)+t.GetWidth()/2
                            for t in b.GetTracks())
                if not blocked: bd.via(f'VS{n}',x+xx,125.5+yy,.6,.3)
        for layer in (F,B):
            bd.rect_zone(layer,f'LOAD{n}',x+2,123,x+10.5,162,priority=5)
        branch(bd,n)
        bd.text(f'CH{n} MAX FUSE {design.CHANNELS[n][0]}A',x+10.6,100,rot=90,size=.8)
    # The common bus remains broad on two layers; no channel receives it
    # directly. Each feed must pass through its local shunt and pass FET.
    for layer in (F,I2):
        bd.rect_zone(layer,'+12V',103,8,326,35,priority=2)
    for ref,x,y,rot,side in [
        ('Q6',96,65,0,'B'),('R21',89,65,0,'B'),('R22',93,61,0,'B'),
        ('R23',99,69,0,'B'),('R24',104,65,0,'B'),('C25',78,46,0,'B'),('C28',78,50,0,'B'),
        ('R25',39,72,0,'B'),('R26',57,72,0,'B'),('R27',61,72,0,'B'),
        ('R28',53,76,0,'B'),('C23',39,76,0,'B'),('C24',48,76,0,'B'),
        ('D8',39,81,0,'B'),('D9',48,81,0,'B')]:
        bd.place(ref,x,y,rot,side)
    for i in range(1,17):
        bd.place(f'TP{i}',28+((i-1)%8)*10,100+((i-1)//8)*12,0,'F')
    for i,(x,y) in enumerate(rev.MOUNTS,1):
        bd.place(f'H{i}',x,y,0,'F'); keepout(bd,x,y)
    for layer in (F,B,I1,I2):
        bd.rect_zone(layer,'GND',.4,.4,rev.W-.4,rev.H-.4,priority=0)
    bd.edge_rect()
    # Board.edge_rect uses legacy geometry; replace outline with current size.
    for d in list(b.GetDrawings()):
        if d.GetLayer()==pcbnew.Edge_Cuts: b.Remove(d)
    for a,c in zip([(0,0),(rev.W,0),(rev.W,rev.H),(0,rev.H)],
                   [(rev.W,0),(rev.W,rev.H),(0,rev.H),(0,0)]):
        d=pcbnew.PCB_SHAPE(); d.SetShape(pcbnew.SHAPE_T_SEGMENT)
        d.SetStart(V(*a)); d.SetEnd(V(*c)); d.SetLayer(pcbnew.Edge_Cuts)
        d.SetWidth(pcbnew.FromMM(.05)); b.Add(d)
    bd.text('eswitch REV C - LOCAL CHANNEL LATCHES',65,126,size=1.3)
    bd.text('40A TOTAL CONTINUOUS TARGET',65,130,size=1.1)
    bd.text('AUTO AND BYPASS ARE BOTH PROTECTED',65,134,size=1.0)
    expected={p.ref for p in design.PARTS if p.footprint}
    assert set(bd.fps)==expected,(expected-set(bd.fps),set(bd.fps)-expected)
    actual=[fp.GetReference() for fp in b.GetFootprints()]
    assert len(actual)==len(set(actual))==len(expected), 'Duplicate or missing footprints'
    sync_metadata(b,NETLIST); apply_rules(b); configure_usb(b)
    # During placement DRC, keep explicitly assigned vias on their intended
    # nets, allowing DRC to report shorts instead of connectivity renaming them.
    for item in b.GetTracks():
        if item.GetClass() == 'PCB_VIA': item.SetIsFree(True)
    save_board(OUT_PCB,b)
    fill_zones(b); save_board(OUT_PCB,b); persist_project_rules(OUT_PCB)
    print(f'Revision C placed: {len(bd.fps)} footprints, {rev.W} x {rev.H}mm')


if __name__=='__main__':
    assert len(sys.argv)==2,'Pass the saved revision B PCB explicitly'
    migrate(Path(sys.argv[1]))
