#!/usr/bin/env python3
"""Two opposed four-channel banks; independent compact placement candidate."""
from pcb_support import *

W,H=136.,104.
MOUNTS=[(4,32),(4,98),(50,5),(50,98),(132,5),(132,36),(132,68),(132,99)]
TARGET=OUT/'compact-placed.kicad_pcb'


def bank_cell(bd,n):
    cx=64+18*((n-1)%4)
    lower=n>4
    def xy(dx,y):return (cx-dx,H-y) if lower else (cx+dx,y)
    def place(ref,dx,y,rot=0,side='B'):
        return bd.place(ref,*xy(dx,y),rot+(180 if lower else 0),side)
    def zone(layer,net,points,priority=4):bd.zone(layer,net,[xy(x,y) for x,y in points],priority=priority,min_th=.2)
    def via(net,dx,y,d=.8,h=.4):bd.via(net,*xy(dx,y),d,h)
    vs,load=f'VS{n}',f'LOAD{n}'
    place(f'F{n}',0,30,0,'F')
    place(f'J{n+10}',3.81,10,180,'F')
    u=place(f'U{n}',0,25)
    # Same local orientation as the checked full-size cells before bank rotation.
    p=bd.pad_pos(f'U{n}','1')
    if (p[1]<25 and not lower) or (p[1]>H-25 and lower):
        u.SetOrientationDegrees(u.GetOrientationDegrees()+180)
    for ref,dx,y,rot in (
        (f'C{n}01',-6,24.6,90),(f'C{n}04',-2.3,29,0),
        (f'R{n}03',-6.2,29.6,90),(f'R{n}04',-6.2,32.8,90),
        (f'R{n}05',-6.2,36,90),(f'C{n}03',-6.2,39.2,90),
        (f'R{n}01',-3.8,33,90),(f'R{n}02',-3.8,36.2,90),
        (f'D{n}01',-5.5,43.5,0),(f'R{n}08',-3.8,47.5,0),(f'R{n}09',.2,47.5,0),
        (f'C{n}02',.2,35.7,90),(f'R{n}06',.2,38.9,0),
        (f'R{n}07',6.5,30,90),(f'D{n}03',6.5,25,0),
        (f'D{n}04',0,4.6,0)):
        place(ref,dx,y,rot)
    place(f'D{n}02',6.5,30,90,'F')
    # Battery trunk enters each centre clip from the inside edge of the bank.
    zone(F,'BATT_RAW',[(-8,30.3),(3.3,30.3),(3.3,34),(-4,34),(-4,53),(-8,53)],3)
    # VS is local to one cell; thermal copper is spread above/under the switch.
    vs_shape=[(-8,13),(1.4,13),(1.4,28.8),(-8,28.8)]
    for layer in (F,I2,B):zone(layer,vs,vs_shape)
    zone(F,vs,[(-3.3,20),(2.8,20),(2.8,44),(-3.3,44)],5)
    # Continuous output strips on both outer layers and In2.
    shape=[(-5.4,8.2),(8.5,8.2),(8.5,43.2),(-3.3,43.2),(-3.3,39.5),(3.5,39.5),(3.5,12.3),(-5.4,12.3)]
    for layer in (F,I2,B):zone(layer,load,shape)
    for y in (16,20,40):
        for dx in (5.2,7.2):via(load,dx,y)
    for y in (18,22,26):
        for dx in (-7,-5):via(vs,dx,y)
    for y in (21.85,28.2):
        for dx in (-.65,.65):via(vs,dx,y,.65,.3)
    for y in (23.1,24.3,25.5,26.7):via(vs,0,y,.6,.3)
    pp=bd.pad_pos
    def track(net,points,w=.3,layer=B):bd.track(layer,net,points,w)
    for ref,pin,net,dx,y in ((f'C{n}01','1',vs,-6,22),(f'C{n}04','1',vs,0,28.2),
                             (f'C{n}02','1',load,4.5,34.75),(f'R{n}06','1',load,4.5,38.9)):
        track(net,[pp(ref,pin),xy(dx,y)],.5)
    # Ground and clamp interfaces are signal-routed after placement.
    for pin,net in (('1',vs),('2','GND')):
        px,py=pp(f'D{n}04',pin)
        for dy in (-1.2,0,1.2):bd.via(net,px,py+dy,.8,.4)
    track(vs,[pp(f'D{n}04','1'),xy(3.4,1.5),xy(-7,1.5),xy(-7,16)],1.5)
    bd.text(f'CH{n}  {10 if n<3 else 20 if n==8 else 5}A MAX',*xy(0,1),size=.8,thick=.12,rot=180 if lower else 0)


def build():
    gen_pcb.NETLIST=str(NETLIST);gen_pcb.ROOT=str(HERE)
    bd=Board()
    for a,b in [((0,0),(W,0)),((W,0),(W,H)),((W,H),(0,H)),((0,H),(0,0))]:bd.line(*a,*b,layer=pcbnew.Edge_Cuts,w=.05)
    for layer in (F,I1,I2,B):bd.rect_zone(layer,'GND',0,0,W,H,priority=0,full=True,min_th=.2,clearance=.2)
    logic(bd)
    bd.fps['C3'].SetPosition(V(39.3,38.3))
    bd.place('J2',45,20,0,'F');bd.place('J3',45,78,0,'F')
    for ref,x,y,rot in [('F9',52,38,0),('D1',48,43,270),('D3',50,51,0),
                       ('U14',28,70,0),('R14',30.5,74,0),('R15',26.5,74,0),('C24',30.5,77,0)]:bd.place(ref,x,y,rot,'B')
    for n in range(1,9):bank_cell(bd,n)
    buck_routes(bd);usb_routes(bd);usb_power_routes(bd)
    for t in bd.b.GetTracks():
        if t.GetClass()!='PCB_TRACK' or t.GetNetname().lstrip('/')!='VBUS':continue
        for get,setter in ((t.GetStart,t.SetStart),(t.GetEnd,t.SetEnd)):
            p=get();x,y=pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
            if abs(y-53.9)<.0001 and x<11:setter(V(x,53.8))
            elif abs(y-49.1)<.0001 and x<11:setter(V(x,49.2))
    pp=bd.pad_pos
    bd.track(B,'BATT_RAW',[pp('F9','1'),(53.4,38),(55.5,35.9),(55.5,30)],1)
    bd.via('BATT_RAW',55.5,30,.8,.4)
    bd.track(B,'LOGIC_FUSED',[pp('F9','2'),(48,38),pp('D1','2')],.8)
    for pin,net in (('1','VIN'),('2','GND')):
        px,py=pp('D3',pin)
        for dy in (-1.5,0,1.5):bd.via(net,px,py+dy,.8,.4)
    bd.via('VIN',48,46,.8,.4)
    bd.track(B,'VIN',[pp('D1','1'),(48,46)],.8)
    bd.track(F,'VIN',[(48,46),(44,46),(40,42),(36.5,40.1)],1)
    bd.track(F,'VIN',[pp('D3','1'),(48,46)],1)
    bd.track(F,'VIN',[(30,59),(38.5,59),(40,57.5),(40,42)],1)
    bd.rect_zone(F,'VIN',52,48.5,54.8,53.5,priority=6,clearance=.2)
    bd.rect_zone(F,'+3V3',25.3,46,43.7,48.1,priority=6,clearance=.2)
    # Main raw feed: short wide upper run and vertical spine; central bus feeds
    # both banks. Native fills reveal local necks for subsequent power review.
    raw=[(37,12),(59,12),(59,44),(129,44),(129,60),(55,60),(51,44),(51,28),(37,28)]
    for layer in (F,I2):bd.zone(layer,'BATT_RAW',raw,priority=2,min_th=.25)
    for x in range(60,130,6):
        for y in (49,55):bd.via('BATT_RAW',x,y,.8,.4)
    for y in range(16,29,4):
        for x in (53,54.5):bd.via('BATT_RAW',x,y,.8,.4)
    for n,(x,y) in enumerate(MOUNTS,1):bd.place(f'H{n}',x,y,0,'F');hole_keepout(bd,x,y)
    for fp in bd.fps.values():
        fp.Reference().SetVisible(False)
        for p in fp.Pads():
            if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH:p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    bd.fps['J4'].SetPosition(V(3.675,51.5))
    for t in bd.b.GetTracks():
        if t.GetClass()=='PCB_VIA':
            p=t.GetPosition();x,y=pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
            if x<=10 and 45<=y<=57:t.SetPosition(V(x-1.325,y))
        else:
            for get,setter in ((t.GetStart,t.SetStart),(t.GetEnd,t.SetEnd)):
                p=get();x,y=pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
                if x<=10 and 45<=y<=57:setter(V(x-1.325,y))
    for item in bd.b.GetDrawings():
        if item.GetClass()=='PCB_TEXT' and item.GetLayer()==B:item.SetLayer(pcbnew.B_SilkS)
    bd.text('BATT+ 9.5-16V',43,10,size=.85)
    bd.text('GND IN',45,88,size=.9)
    bd.text('MOVE FUSES WITH POWER OFF',91,52,size=.8)
    bd.text('40A TOTAL TARGET',28,92,size=.8)
    configure_usb(bd.b)
    assert set(bd.comps)==set(bd.fps)
    sync_metadata(bd.b,str(NETLIST))
    bd.b.BuildConnectivity()
    TARGET.with_suffix('.kicad_pro').write_text((HERE/'eswitch-simple.kicad_pro').read_text())
    save_board(TARGET,bd.b)
    print(f'Compact candidate: {W} x {H} mm; {len(bd.fps)} footprints; {100*(1-W*H/(228*90)):.1f}% less PCB area')


if __name__=='__main__':build()
