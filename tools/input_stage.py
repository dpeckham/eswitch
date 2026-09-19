"""Revision B input: reverse ideal diode, Kelvin shunt, power-limit/latch switch.

This module is shared by the full layout generator and the one-time migration
that preserves existing signal routes. All coordinates are board millimetres.
"""
import pcbnew
from gen_pcb import CX, STUD_12V, STUD_GND

F, B, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In2_Cu
REFS = {"J2", "J3", "Q1", "Q2", "Q3", "Q4", "U12", "U14", "R20", "D3", "D6", "D7", "F9", "D1"}
REFS.update(f"R{n}" for n in range(12, 20))
REFS.update(f"C{n}" for n in range(15, 20))


def main_power(bd):
    from layout_revision_b import orient_source
    bd.place("J2", *STUD_12V, 0, "F").Reference().SetVisible(False)
    bd.place("J3", *STUD_GND, 0, "F").Reference().SetVisible(False)
    for ref, x, y in (("Q1",57.8,10),("Q2",57.8,23)):
        bd.place(ref,x,y,0,"B")
        orient_source(bd,ref,True)
    # LFPAK88: pin 1 is gate, 2/3/4 sources, 5 mounting-base drain.
    for ref,y in (("Q3",10),("Q4",23)):
        bd.place(ref,94,y,0,"B")
        if bd.pad_pos(ref,"2")[0] < bd.pad_pos(ref,"5")[0]:
            fp=bd.fps[ref]
            fp.SetOrientationDegrees(fp.GetOrientationDegrees()+180)
    for ref,x,y,rot in (
        ("R20",74,17.3,180),("U12",63.5,31.8,180),("U14",84.5,34.5,270),
        ("C15",50.7,30,90),("C16",67.7,34.5,90),("C17",63.5,37,0),
        ("C18",82,40,0),("C19",103,29.5,90),
        ("R12",84,43,90),("R13",84,46.5,90),("R14",93,38.5,0),("R15",93,41.5,180),
        ("R17",89,42,90),("R18",89,45.2,90),
        ("R16",100.5,7,0),("R19",100.5,20,0),
        ("D3",43,31,0),("D6",111,28.5,0),("D7",113,40,270),
        ("F9",100,47,0),("D1",75,42.5,0),
    ):
        bd.place(ref,x,y,rot,"B")
    assert bd.pad_pos("R20","1")[0] < bd.pad_pos("R20","2")[0]
    for layer in (F,I2,B):
        bd.rect_zone(layer,"BATT_RAW",35.5,3,56,27.5,priority=3)
        bd.rect_zone(layer,"BATT_MID",56.7,3,72,27.5,priority=3)
        bd.rect_zone(layer,"BATT_SENSE",76,3,95.5,28.8,priority=3)
        bd.rect_zone(layer,"+12V",96.2,3,121.5,32,priority=3)
    for layer in (F,I2):
        bd.rect_zone(layer,"+12V",99,8,CX[-1]+7.62,27,priority=2)
    for y0 in (10,23):
        for x in (53.2,54.2):
            for dy in (-.3,.9,2.1):
                bd.via("BATT_RAW",x,y0+dy,.8,.4)
        for x in (60,61.2,62.4):
            for dy in (-3.2,3.2):
                bd.via("BATT_MID",x,y0+dy,.8,.4)
        for x in (89,90.2,91.4,92.6,93.8):
            for dy in (-5.1,5.1):
                bd.via("BATT_SENSE",x,y0+dy,.8,.4)
        for x in (99.5,100.7,101.9):
            for dy in (-.5,1,2.5,4):
                bd.via("+12V",x,y0+dy,.8,.4)
    # Spread shunt-terminal current into all three positive-power layers.
    for net,xs in (("BATT_MID",(66.8,68)),("BATT_SENSE",(80,81.2))):
        for x in xs:
            for y in (13.9,15.1,16.3,17.5,18.7):
                bd.via(net,x,y,.8,.4)
    bd.text("BATT+ 9.5-16V",43,7.7,size=1.0)
    bd.text("GND IN",51,42.5,size=1.2)
    bd.text("UPSTREAM FUSE REQUIRED",62,61,size=1.1)
    bd.text("40A TOTAL TARGET / SEE TEST LIMITS",65,64,size=.8)
    bd.text("FAULT: CYCLE BATTERY",102,57,size=1)


def protection_routes(bd, include_vin=True):
    pp=bd.pad_pos
    def wire(layer,net,points,width=.25):
        bd.track(layer,net,points,width)
    def escape(ref,pin,net,points,diameter=.5,width=.2):
        wire(B,net,[pp(ref,pin),*points],width)
        bd.via(net,*points[-1],diameter,.3)

    for ref in ("Q1","Q2"):
        x,y=pp(ref,"4")
        wire(B,"DGATE_MAIN",[(x,y),(51.8,y),(51.8,27.5)])
    wire(B,"DGATE_MAIN",[(51.8,27.5),(51.8,33.85),(60.5,33.85),(61.3,33.05),pp("U12","1")],.2)
    escape("U12","2","BATT_RAW",[(60.8,32.55)])
    escape("U12","6","BATT_RAW",[(61.1,30.55),(60.5,29.95)])
    wire(F,"BATT_RAW",[(60.8,32.55),(59.4,32.55),(58.7,31.85),(58.7,29.95),(60.5,29.95)],.3)
    wire(F,"BATT_RAW",[(58.7,29.95),(54.5,29.95),(54.5,26.7)],.3)
    wire(B,"BATT_RAW",[pp("C15","1"),(50.7,26.7)],.5)
    wire(B,"BATT_RAW",[pp("D3","1"),(46.4,26)],3)
    for pin in ("3","4"):
        wire(B,"BATT_MID",[pp("U12",pin),(61.5,pp("U12",pin)[1]),(61.25,31.8),(60.6,31.8)],.2)
    bd.via("BATT_MID",60.6,31.8,.5,.3)
    wire(F,"BATT_MID",[(60.6,31.8),(61.2,31.2),(61.2,27)],.3)
    for pin in ("9","10"):
        wire(B,"BATT_MID",[pp("U12",pin),(65.5,pp("U12",pin)[1]),(65.75,31.8),(66.1,31.8)],.2)
    bd.via("BATT_MID",66.1,31.8,.5,.3)
    wire(F,"BATT_MID",[(66.1,31.8),(67,30.9),(67,27)],.5)
    escape("U12","12","BATT_MID",[(65.05,33.45),(65.05,34.1)])
    wire(F,"BATT_MID",[(65.05,34.1),(66.1,33.05),(66.1,31.8)],.3)
    escape("C16","1","BATT_MID",[(67.7,32.8)],.6,.3)
    wire(F,"BATT_MID",[(67.7,32.8),(66.1,31.8)],.4)
    escape("C17","2","BATT_MID",[(61.2,37)],.6,.3)
    wire(F,"BATT_MID",[(61.2,37),(63.4,34.8),(64.35,34.8),(65.05,34.1)],.3)
    wire(B,"CAP_MAIN",[pp("U12","11"),(65.5,32.55),(65.9,32.95),(65.9,35.8),pp("C17","1")],.2)

    # Four-terminal Kelvin traces are paired on F.Cu; load copper only contacts
    # R20 power pads. U14's supply is taken from its Kelvin terminal, as TI shows.
    for pin,net in (("3","HS_VCC"),("4","HS_SENSE")):
        px,py=pp("R20",pin)
        wire(B,net,[(px,py),(px,23)],.25)
        bd.via(net,px,23,.6,.3)
    wire(F,"HS_VCC",[(69.975,23),(69.975,30.8),(86.45,30.8),(86.45,29.5)],.25)
    wire(F,"HS_SENSE",[(78.025,23),(78.025,24.4),(85.8,24.4),(85.8,28.5)],.25)
    for pin,net,y in (("14","HS_VCC",29.5),("13","HS_SENSE",28.5)):
        x,py=pp("U14",pin)
        escape("U14",pin,net,[(x,y)],.5,.2)
    for ref,r,y in (("Q3","R16",7),("Q4","R19",20)):
        wire(B,f"GATE_{ref}",[pp(ref,"1"),pp(r,"2")],.3)
        wire(B,"HGATE_MAIN",[pp(r,"1"),(104.3,y),(104.3,32.7)],.3)
    escape("U14","12","HGATE_MAIN",[(85.15,30.2)],.5,.2)
    bd.via("HGATE_MAIN",104.3,32.7,.6,.3)
    wire(I2,"HGATE_MAIN",[(85.15,30.2),(104.3,30.2),(104.3,32.7)],.3)
    escape("U14","11","+12V",[(84.5,30.1),(83.8,29.4)],.5,.2)
    wire(I2,"+12V",[(83.8,29.4),(83.8,33),(100,33),(100,31)],.3)
    bd.via("+12V",100,31,.6,.3)

    # Quiet dividers/programming are below the controller; no current-path cuts.
    for top,bottom,net in (("R12","R13","OV_MAIN"),("R14","R15","UV_MAIN"),("R17","R18","HS_PROG")):
        wire(B,net,[pp(top,"2"),pp(bottom,"1")])
    wire(B,"UV_MAIN",[pp("U14","1"),(86.45,38.5),pp("R14","2")])
    wire(B,"HS_REF",[pp("U14","2"),(85.8,39.2),(87.3,40.7),(89,40.7),pp("R17","1")])
    wire(B,"HS_PROG",[pp("U14","3"),(85.15,40.4),(87.1,42.35),(87.1,43.8),(89,43.8)])
    wire(B,"HS_TIMER",[pp("U14","4"),(84.5,39.1),(83.6,40),pp("C18","1")])
    wire(B,"OV_MAIN",[pp("U14","5"),(83.85,38.5),(79,38.5),(79,40.3),(81,42.3),(81,43.825),pp("R12","2")])
    for ref,point in (("R12",(84,41)),("R14",(95,38.5))):
        escape(ref,"1","BATT_MID",[point],.6,.3)
    bd.via("BATT_MID",68,26,.6,.3)
    wire(I2,"BATT_MID",[(68,26),(68,28),(77,28),(77,36.5),(84,36.5),(84,41)],.4)
    wire(I2,"BATT_MID",[(84,36.5),(95,36.5),(95,38.5)],.4)
    for ref,pin,x,y in (("C15","2",49.5,31.2),("C16","2",69,35.45),
                        ("C18","2",81.05,41.3),("C19","2",103,31.8),
                        ("R13","2",85.3,47.325),("R15","2",95,41.5),
                        ("R18","2",89,47.3),("U12","5",59.6,31.05),
                        ("U12","7",65.1,29.7),("U14","7",81.5,37.3625)):
        escape(ref,pin,"GND",[(x,y)],.5,.2)
    for ref in ("D3","D6"):
        gx,gy=pp(ref,"2")
        for dx in (-.6,.6):
            for dy in (-2.3,2.3):
                bd.via("GND",gx+dx,gy+dy,.8,.4)
                wire(B,"GND",[(gx,gy),(gx+dx,gy+dy)],.7)
    for pin in ("1","3"):
        x,y=pp("D7",pin)
        for dx in (-1.3,1.3):
            for dy in (-1.2,0,1.2):
                bd.via("GND",x+dx,y+dy,.8,.4)
                wire(B,"GND",[(x,y),(x+dx,y+dy)],.8)
    dx,dy=pp("D7","2")
    wire(B,"+12V",[(dx,dy),(dx,31)],6)
    wire(B,"+12V",[pp("C19","1"),(103,27)],.5)
    wire(B,"+12V",[pp("F9","1"),(105.8,47),(105.8,34),(111,34)],1.5)
    escape("F9","2","V12F",[(97,47)],.9,1)
    escape("D1","2","V12F",[(72,41)],.9,1)
    wire(I2,"V12F",[(97,47),(95.2,48.8),(72,48.8),(72,41)],1)
    if include_vin:
        bd.via("VIN",79.5,42.5,.9,.45)
        wire(B,"VIN",[pp("D1","1"),(79.5,42.5)],1)
        wire(F,"VIN",[(79.5,42.5),(79.5,46),(72,53.5),(60,53.5),(60,63),
                      (42,63),(39,60),(38.5,59.5),(38.5,41.7),(36.5,40.1)],1)
