"""Revision B placement and manually defined power copper. Dimensions in mm.

This is the release layout generator; the old revision-A build() in gen_pcb.py is
retained temporarily for comparison, not used by the build recipe.
"""
import json
from pathlib import Path
import pcbnew
import design
from gen_pcb import Board, V, W, H, CX, CELL0, Y_FUSE, Y_TERM, Y_BTS, STUD_12V, STUD_GND
from gen_pcb import ROOT, NETLIST, OUT_PCB, persist_project_rules, fuse_silk_labels
from pcb_nets import sync_metadata
from pcb_io import save_board
from fabrication_rules import configure_usb

F, B, I1, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu


def orient_source(bd, ref, left):
    fp = bd.fps[ref]
    sx = bd.pad_pos(ref, "1")[0]
    dx = bd.pad_pos(ref, "5")[0]
    if (sx < dx) != left:
        fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)


def channel(bd, n):
    cx = CX[n-1]
    bd.place(design.OUTPUT_REFS[n-1], cx-3.81, Y_TERM, 0, "F").Reference().SetVisible(False)
    bd.place(f"F{n}", cx, Y_FUSE, 0, "F").Reference().SetVisible(False)
    u = bd.place(f"U{n}", cx, Y_BTS, 0, "B")
    if bd.pad_pos(f"U{n}", "8")[0] < bd.pad_pos(f"U{n}", "1")[0]:
        u.SetOrientationDegrees(180)
    if bd.pad_pos(f"U{n}", "1")[1] < Y_BTS:
        u.SetOrientationDegrees(u.GetOrientationDegrees()+180)
    for ref, dx, y, rot in (
        (f"C{n}01",-6,34.6,90), (f"C{n}04",-2.3,39,0),
        (f"R{n}03",-6.2,39.6,90), (f"R{n}04",-6.2,42.8,90),
        (f"R{n}05",-6.2,46,90), (f"C{n}03",-6.2,49.2,90),
        (f"R{n}01",-3.8,43,90), (f"R{n}02",-3.8,46.2,90),
        (f"R{n}08",-2.6,55,0), (f"D{n}01",-2.6,51.5,0),
        (f"C{n}02",.2,42.5,90), (f"R{n}06",.2,46,90),
        (f"R{n}07",5.3,19,90), (f"D{n}02",5.3,23.4,90),
    ):
        bd.place(ref, cx+dx, y, rot, "B")
    for ref in (f"C{n}01", f"R{n}07"):
        bd.pin_up(ref)
    bd.pin_up(f"D{n}02", "2")
    vs, load = f"VS{n}", f"LOAD{n}"
    # Fuse AUTO blade to VS. The long side strip is paralleled on In2 for CH8.
    vs_poly = [(cx-7.1,3.8),(cx+3.4,3.8),(cx+3.4,8.2),(cx-3.5,8.2),
               (cx-3.5,30.8),(cx+1.3,30.8),(cx+1.3,38.7),(cx-1.3,38.7),
               (cx-1.3,31.8),(cx-7.1,31.8)]
    bd.zone(B, vs, vs_poly, priority=3, min_th=.3)
    # Broad opposite-side spreader plus vias just beyond the exposed pad ends.
    bd.rect_zone(F, vs, cx-7.1,30.2,cx+1.3,58.0,priority=3)
    for y in (31.85,38.2):
        for dx in (-.65,.65):
            bd.via(vs,cx+dx,y,.65,.3)
    for y in (10,14,18,22,26,30):
        bd.via(vs,cx-5.2,y,.8,.4)
    load_poly = [(cx-3.3,26.9),(cx+7.1,26.9),(cx+7.1,71.5),(cx+2,71.5),
                 (cx+2,30.3),(cx-3.3,30.3)]
    bd.zone(B,load,load_poly,priority=3,min_th=.3)
    # Parallel output copper on the front; no foreign signal routing across it.
    bd.rect_zone(F,load,cx+2,32,cx+7.1,71.5,priority=3)
    for y in (34,38,42,46,50,54,58,62,66):
        bd.via(load,cx+5.9,y,.8,.4)
    for ref in (f"C{n}01",):
        x,y=bd.pad_pos(ref,"1")
        bd.track(B,vs,[(x,y),(x,31.3)],.5)
    x,y=bd.pad_pos(f"C{n}04","1")
    bd.track(B,vs,[(x,y),(cx,39),(cx,38.2)],.4)
    for ref in (f"C{n}02",f"R{n}06"):
        x,y=bd.pad_pos(ref,"1")
        bd.track(B,load,[(x,y),(cx+2.6,y)],.5)
    x,y=bd.pad_pos(f"R{n}07","1")
    bd.track(B,load,[(x,y),(x,16.6),(cx+3.9,16.6),(cx+3.9,28.5)],.5)
    if n == 8:
        bd.zone(I2,vs,vs_poly,priority=4,min_th=.3)
        bd.rect_zone(B,load,cx+2,27,cx+10.5,71.5,priority=4)
        bd.rect_zone(I2,load,cx+2,30,cx+10.5,71.5,priority=4)
        for y in (34,38,42,46,50,54,58,62,66):
            bd.via(load,cx+8.8,y,.9,.45)
        for y in (10,14,18,22,26,30):
            bd.via(vs,cx-6.4,y,.8,.4)
    bd.text(f"CH{n}",cx,61.5,size=1.2)
    bd.text("-",cx-3.81,63.5,size=1.2,thick=.25)
    bd.text("+",cx+3.81,63.5,size=1.2,thick=.25)


def obsolete_main_power(bd):
    bd.place("J2",*STUD_12V,0,"F").Reference().SetVisible(False)
    bd.place("J3",*STUD_GND,0,"F").Reference().SetVisible(False)
    for ref,x,y in (("Q1",57.8,10), ("Q2",57.8,23), ("Q3",69.2,10), ("Q4",69.2,23)):
        bd.place(ref,x,y,0,"B")
        orient_source(bd,ref,ref in ("Q1","Q2"))
    bd.place("U12",63.5,31.8,180,"B")
    for ref,x,y,rot in (
        ("C15",50.7,30,90), ("C16",67.7,34.5,90), ("C17",63.5,37,0),
        ("C18",71.5,32,90), ("C19",75.0,31,90),
        ("R12",57.5,34.8,90), ("R13",57.5,38,90),
        ("R14",57.8,29.2,90), ("R15",54.8,29.2,90), ("R16",68.5,30.5,90),
        ("D3",43,31,0), ("D6",81.5,29.6,0), ("F9",82,38,0), ("D1",75,42.5,0),
    ):
        bd.place(ref,x,y,rot,"B")
    # Main three conductors are paralleled on F.Cu/In2/B.Cu; In1 stays GND.
    for layer in (F,I2,B):
        bd.rect_zone(layer,"BATT_RAW",35.5,3,56,27.5,priority=3)
        bd.rect_zone(layer,"BATT_MID",56.7,3,70.3,27.5,priority=3)
        bd.rect_zone(layer,"+12V",71,3,89.5,32,priority=3)
    for layer in (F,I2):
        bd.rect_zone(layer,"+12V",73,8,CX[-1]+7.62,27,priority=2)
    # Symmetric via banks next to MOSFETs; no open holes in paste pads.
    for y0 in (10,23):
        for dx in (-.5,.5):
            for dy in (-.3,.9,2.1):
                bd.via("BATT_RAW",53.7+dx,y0+dy,.8,.4)
            for dy in (-1.6,-.4,.8):
                bd.via("+12V",73.3+dx,y0+dy,.8,.4)
        for x in (60,61.2,62.4,64.6,65.8,67):
            for y in (y0-3.2,y0+3.2):
                bd.via("BATT_MID",x,y,.8,.4)
    bd.text("BATT+ 9-16V",43,7.7,size=1.0)
    bd.text("GND IN",51,42.5,size=1.2)
    bd.text("UPSTREAM FUSE REQUIRED",62,61,size=1.1)
    bd.text("40A TOTAL TARGET / SEE TEST LIMITS",65,64,size=.8)


def logic(bd):
    # Antenna overhang and retained all-layer copper exclusion at the top edge.
    bd.place("U10",12,8.6,0,"B")
    for ref,x,y,rot in (
        ("C10",23.4,4.6,180),("C9",24,12.7,90),
        ("R5",9,30,0),("C11",12,30,0),("R6",15,30,0),
        ("D5",5,25,0),("R9",8.5,25,0),
        ("U9",32,43,0),("C1",27.5,42.4,90),("C2",36.5,42.4,90),
        ("C3",39,39,90),("C7",27,48.8,90),("C8",32,48.8,90),
        ("C12",37,48.8,90),("C13",42,48.8,90),
        ("R1",35.8,38,180),("C14",29.8,37.3,0),("NT1",32,38,270),
        ("Q5",25,61,0),("U13",25,55,0),("C20",17,58,90),
        ("C21",30,55,90),("C22",20,55,90),
        ("J4",5,51.5,270),("U11",13,51.5,0),
        ("R7",11.9,54.75,0),("R8",11.9,48.25,0),
        ("R10",23.8,20.05,0),("R11",23.8,18.45,0),
    ):
        bd.place(ref,x,y,rot,"B")
    bd.place("SW1",12.5,30,0,"F")
    bd.place("SW2",12.5,38.5,0,"F")
    bd.place("J5",33.5,64,0,"F")
    orient_source(bd,"Q5",True)
    assert bd.pad_pos("J4","A4")[0]>5
    for ref in ("R7","R8"):
        fp=bd.fps[ref]
        if bd.pad_pos(ref,"1")[0]>bd.pad_pos(ref,"2")[0]:
            fp.SetOrientationDegrees(fp.GetOrientationDegrees()+180)
    bd.text("USB: BENCH ONLY",12,70,layer=B,size=.9)
    bd.text("DISCONNECT BATTERY",12,72,layer=B,size=.9)
    bd.text("RESET",12.5,25.2,size=.8)
    bd.text("BOOT",12.5,43,size=.9)
    bd.text("G 3 T R",30.5,66,rot=90,size=.8)


def buck_routes(bd):
    """Local loops following TI's symmetric VIN/PGND layout; all on B.Cu."""
    pp=bd.pad_pos
    # Short, wide input loops on both sides of the integrated power module.
    bd.track(B,"VIN",[pp("C1","1"),(28.9,42.325),(30.225,42.325)],.6)
    bd.track(B,"VIN",[(30.225,42.025),(30.225,42.675)],.3)
    bd.track(B,"VIN",[pp("C2","1"),(35.1,42.325),(33.775,42.325)],.6)
    bd.track(B,"VIN",[(33.775,41.225),(33.775,42.675)],.3)
    # Bridge the two inputs outside the quiet pin row, on F.Cu.
    for x in (27.5,36.5):
        bd.via("VIN",x,40.1,.65,.3)
        bd.track(B,"VIN",[(x,40.1),(x,40.925)],.6)
    bd.track(I2,"VIN",[(27.5,40.1),(36.5,40.1)],.8)
    bd.track(B,"VIN",[pp("C3","1"),(40.5,38.225),(40.5,41),(39,42.5),(38.3,42.5),(36.5,40.925)],.4)
    # PGND spine ties the two internal pads and both sides to input capacitor ground.
    bd.rect_zone(B,"GND",30.8,41.9,33.2,44.25,priority=6,min_th=.18,clearance=.2)
    bd.track(B,"GND",[pp("U9","28"),pp("U9","29")],1)
    for x in (30.9,33.1):
        bd.via("GND",x,43.25,.55,.3)
        bd.track(B,"GND",[(32,43.25),(x,43.25)],.45)
    for cx,px in ((27.5,30.225),(36.5,33.775)):
        bd.track(B,"GND",[(cx,43.875),(px,43.875)],.6)
        bd.track(B,"GND",[(px,43.475),(px,44.125)],.3)
        bd.track(B,"GND",[(px,43.875),(32,43.6)],.4)
        for dy in (-.5,.5):
            bd.via("GND",cx,43.875+dy,.65,.3)
    # VOUT copper reaches all output lands but clears the deliberately isolated SW land.
    bd.rect_zone(B,"+3V3",29.7,44.5,34.3,48.0,priority=6,min_th=.18,clearance=.2)
    bd.rect_zone(B,"+3V3",25.3,46.5,43.7,48.1,priority=7,min_th=.18,clearance=.2)
    for x in (27,32,37,42):
        bd.via("+3V3",x,46.85,.65,.3)
        bd.via("GND",x,50.8,.65,.3)
        bd.track(B,"GND",[(x,50.275),(x,50.8)],.6)
    # Quiet analog ground is a separate island, star-connected to PGND via NT1.
    bd.track(B,"AGND_BUCK",[pp("U9","27"),pp("U9","24"),pp("NT1","1")],.25)
    bd.via("AGND_BUCK",37.5,38,.6,.3)
    bd.via("AGND_BUCK",32,38.5,.6,.3)
    bd.track(B,"AGND_BUCK",[pp("R1","2"),(37.5,38)],.25)
    bd.track(F,"AGND_BUCK",[(37.5,38),(37,38.5),(32,38.5)],.25)
    bd.via("GND",33.1,37.5,.6,.3)
    bd.track(B,"GND",[pp("NT1","2"),(33.1,37.5)],.35)
    bd.track(B,"RT",[pp("U9","1"),(34.4,40.575),(34.4,38.575),pp("R1","1")],.25)
    bd.track(B,"VCC_BUCK",[pp("U9","23"),(31.5,39),pp("C14","1")],.25)
    bd.via("GND",28.7,37.3,.6,.3)
    bd.track(B,"GND",[pp("C14","2"),(28.7,37.3)],.35)
    # Fixed-output FB is a Kelvin sense from the output-capacitor node, not a switch node.
    bd.track(B,"+3V3",[pp("U9","25"),(32.5,39.2),(33,39.2)],.2)
    bd.via("+3V3",33,39.2,.6,.3)
    bd.track(F,"+3V3",[(33,39.2),(34.8,41),(34.8,45.05),(33,46.85),(32,46.85)],.4)
    bd.track(B,"+3V3",[pp("U9","22"),(31,39.2),(29.5,39.2)],.2)
    bd.via("+3V3",29.5,39.2,.6,.3)
    bd.track(F,"+3V3",[(29.5,39.2),(33,39.2)],.4)


def usb_routes(bd):
    pp=bd.pad_pos
    # Connector's interleaved duplicated USB2 contacts: two short opposing escapes.
    bd.track(B,"USB_D+",[pp("J4","A6"),(7.68,51.75),(7.68,50.75),pp("J4","B6"),
                         (10,50.75),pp("U11","6"),pp("U11","1")],.25)
    bd.track(B,"USB_D-",[pp("J4","A7"),(9.68,51.25),(9.68,52.25),pp("J4","B7")],.25)
    bd.track(B,"USB_D-",[(9.68,51.75),(10.68,51.75),(11.38,52.45),pp("U11","4"),pp("U11","3")],.25)
    # Main pair: 0.25 mm tracks, 0.20 mm edge gap; paired 45-degree corners.
    bd.track(B,"USB_D+",[pp("R10","1"),(25.825,21.05),(25.825,29.175),(24.5,30.5),
                         (24.5,45.05),(19,50.55),pp("U11","1")],.25)
    bd.track(B,"USB_D-",[pp("R11","1"),(26.275,20.23),(26.275,29.3614),(24.95,30.6864),
                         (24.95,45.2364),(19.1864,51),(16.65,51),(15.2,52.45),pp("U11","3")],.25)
    bd.track(B,"USB_MCU_D+",[pp("R10","2"),pp("U10","14")],.25)
    bd.track(B,"USB_MCU_D-",[pp("R11","2"),pp("U10","13")],.25)
    bd.via("GND",15.1,51.25,.65,.3)
    bd.track(B,"GND",[pp("U11","2"),(15.1,51.25)],.35)
    # VBUS joins behind the connector pin row; preserve clearances to both locating pegs.
    bd.track(B,"VBUS",[pp("J4","A4"),(8.13,53.9),(6.93,53.3),
                       (6.93,49.7),(8.13,49.1),pp("J4","A9")],.3)
    bd.track(B,"VBUS",[pp("J4","A4"),(10,53.9),(10,54.1)],.3)
    bd.via("VBUS",10,54.1,.6,.3)
    bd.via("VBUS",12.95,51.5,.6,.3)
    bd.track(B,"VBUS",[pp("U11","5"),(12.95,51.5)],.3)
    bd.track(F,"VBUS",[(10,54.1),(12.95,54.1),(12.95,51.5)],.5)
    bd.track(B,"CC1",[pp("J4","A5"),(9.75,52.75),(10.9,53.9),pp("R7","1")],.25)
    bd.track(B,"CC2",[pp("J4","B5"),(9.75,49.75),(10.9,48.6),pp("R8","1")],.25)


def obsolete_main_gate_routes(bd):
    # Gate paths intentionally run on B.Cu; parallel F/In2 source copper remains intact.
    for ref in ("Q1","Q2"):
        x,y=bd.pad_pos(ref,"4")
        bd.track(B,"DGATE_MAIN",[(x,y),(51.8,y),(51.8,27.5)],.25)
    bd.track(B,"DGATE_MAIN",[(51.8,27.5),(51.8,33.05),bd.pad_pos("U12","1")],.25)
    for ref in ("Q3","Q4"):
        x,y=bd.pad_pos(ref,"4")
        bd.track(B,"HGATE_MAIN",[(x,y),(74.8,y),(74.8,26.7)],.25)
    bd.track(B,"HGATE_MAIN",[(74.8,26.7),(70,26.7),(66.7,30),
                              (66.7,31.05),bd.pad_pos("U12","8")],.25)


def obsolete_protection_routes(bd):
    pp=bd.pad_pos
    bd.track(B,"BATT_RAW",[pp("U12","2"),pp("U12","3"),(60.9,32.05),(60.9,32.25)],.2)
    bd.via("BATT_RAW",60.9,32.25,.5,.3)
    bd.track(F,"BATT_RAW",[(60.9,32.25),(60.9,30.3),(49.5,30.3),(49.5,26.7)],.5)
    bd.track(B,"BATT_RAW",[pp("C15","1"),(50.7,26.7)],.5)
    bd.track(B,"BATT_RAW",[pp("D3","1"),(46.4,26)],3)
    bd.via("BATT_RAW",57.8,27.4,.6,.3)
    bd.track(B,"BATT_RAW",[pp("R14","1"),(57.8,27.4)],.25)
    bd.track(F,"BATT_RAW",[(57.8,27.4),(55,27.4),(55,26.5)],.4)
    bd.track(B,"UV_MAIN",[pp("U12","6"),(60.6,30.55),(60.075,30.025),pp("R14","2"),
                           (56.1,30.025),(55.5,28.375),pp("R15","1")],.2)
    bd.track(B,"OV_TOP",[pp("U12","4"),(60.2,31.55),(59.9,31.65)],.2)
    bd.via("OV_TOP",59.9,31.65,.5,.3)
    bd.via("OV_TOP",59,33.975,.5,.3)
    bd.track(F,"OV_TOP",[(59.9,31.65),(59.9,33.075),(59,33.975)],.2)
    bd.track(B,"OV_TOP",[(59,33.975),pp("R12","1")],.2)
    bd.track(B,"OV_MAIN",[pp("U12","5"),(59,31.05)],.2)
    bd.via("OV_MAIN",59,31.05,.5,.3)
    bd.via("OV_MAIN",59,36.4,.5,.3)
    bd.track(F,"OV_MAIN",[(59,31.05),(58.2,31.85),(58.2,35.6),(59,36.4)],.2)
    bd.track(B,"OV_MAIN",[pp("R12","2"),pp("R13","1")],.3)
    bd.track(B,"OV_MAIN",[(57.5,36.4),(59,36.4)],.2)
    bd.track(B,"HGATE_MAIN",[pp("R16","1"),(67.5,29.675),(66.7,30)],.25)
    bd.track(B,"SLEW_MAIN",[pp("R16","2"),(70,31.325),pp("C18","1")],.3)
    bd.track(B,"+12V",[pp("U12","9"),(67.5,31.55)],.2)
    bd.via("+12V",67.5,31.55,.5,.3)
    bd.track(F,"+12V",[(67.5,31.55),(72,31.55)],.5)
    bd.track(B,"BATT_MID",[pp("U12","10"),(66.7,32.05),(66.7,32.15)],.2)
    bd.via("BATT_MID",66.7,32.15,.5,.3)
    bd.track(B,"BATT_MID",[pp("U12","12"),(64.9375,34.2)],.2)
    bd.via("BATT_MID",64.9375,34.2,.6,.3)
    bd.via("BATT_MID",67.7,32.9,.6,.3)
    bd.track(B,"BATT_MID",[(67.7,32.9),pp("C16","1")],.3)
    bd.track(F,"BATT_MID",[(66.5,26.5),(66.5,31.6),(66.7,32.15),(64.9375,34.2),(62.025,37)],.5)
    bd.track(F,"BATT_MID",[(66.7,32.15),(67.7,32.9)],.4)
    bd.via("BATT_MID",61,37,.6,.3)
    bd.track(F,"BATT_MID",[(61,37),(62.025,37)],.4)
    bd.track(B,"BATT_MID",[(61,37),pp("C17","2")],.4)
    bd.track(B,"CAP_MAIN",[pp("U12","11"),(66.3,32.55),
                            (66.3,35.675),pp("C17","1")],.2)
    bd.track(B,"+12V",[pp("F9","1"),(86.5,38),(86.5,31)],1.5)
    bd.track(B,"V12F",[pp("F9","2"),(78.5,38),(74,38),(73,39),pp("D1","2")],1)
    bd.via("VIN",79.5,42.5,.9,.45)
    bd.track(B,"VIN",[pp("D1","1"),(79.5,42.5)],1)
    bd.track(F,"VIN",[(79.5,42.5),(79.5,46),(72,53.5),(60,53.5),(60,63),(42,63),
                      (39,60),(38.5,59.5),(38.5,41.7),(36.5,40.1)],1)
    # Return vias outside paste apertures, including short paths for both TVSs.
    for ref,pin,vx,vy in (("C15","2",49.5,31.2), ("R15","2",54.8,31.3),
                          ("R13","2",57.5,40), ("C16","2",69,35.45),
                          ("C18","2",71.5,34.4), ("C19","2",75,33.5),
                          ("U12","7",65.6,30.1)):
        bd.track(B,"GND",[pp(ref,pin),(vx,vy)],.25)
        bd.via("GND",vx,vy,.6,.3)
    for ref in ("D3","D6"):
        gx,gy=pp(ref,"2")
        for dx in (-.6,.6):
            for dy in (-2.3,2.3):
                bd.via("GND",gx+dx,gy+dy,.8,.4)
                bd.track(B,"GND",[(gx,gy),(gx+dx,gy+dy)],.7)


def usb_power_routes(bd):
    pp=bd.pad_pos
    bd.rect_zone(B,"VBUS",20.5,60,23.7,64.8,priority=5,clearance=.2)
    bd.rect_zone(B,"VIN",24,57.8,30.7,64.8,priority=5,clearance=.2)
    bd.via("VIN",30,59,.8,.4)
    bd.track(F,"VIN",[(30,59),(38.5,59)],1)
    bd.track(B,"VBUS",[pp("C20","1"),(15.5,57.05),(15.5,62),(19.5,62),(22.175,62)],.8)
    bd.track(B,"VBUS",[(19.5,61),(19.5,62)],.8)
    bd.via("VBUS",19.5,61,.8,.4)
    bd.track(F,"VBUS",[(10,54.1),(12,56.1),(14.6,56.1),(19.5,61)],.8)
    bd.track(B,"DGATE_USB",[pp("U13","1"),(26.5,52.9)],.2)
    bd.via("DGATE_USB",26.5,52.9,.5,.3)
    bd.via("DGATE_USB",20.5,59.095,.5,.3)
    bd.track(F,"DGATE_USB",[(26.5,52.9),(26.5,52.3),(20.5,52.3),(18.5,54.3),(18.5,57.1),(20.5,59.095)],.2)
    bd.track(B,"DGATE_USB",[(20.5,59.095),pp("Q5","4")],.2)
    for pin,x,y in (("2",27.5,54.1),("6",26.95,56.5)):
        path=[pp("U13",pin),(27.3,54.25),(x,y)] if pin=="2" else [pp("U13",pin),(x,y)]
        bd.track(B,"VBUS",path,.2)
        bd.via("VBUS",x,y,.5,.3)
    bd.track(F,"VBUS",[(27.5,54.1),(26.95,54.65),(26.95,58),(23.5,58),(20.5,61),(19.5,61)],.5)
    bd.track(B,"VIN",[pp("U13","3"),pp("U13","4"),(28.5,55.25),pp("C21","1")],.2)
    bd.via("VIN",30,53.1,.6,.3)
    bd.track(B,"VIN",[pp("C21","1"),(30,53.1)],.4)
    bd.track(I2,"VIN",[(30,53.1),(30,59)],.6)
    bd.track(B,"VIN",[pp("U13","12"),(22.9,53.15)],.2)
    bd.via("VIN",22.9,53.15,.5,.3)
    bd.track(B,"VIN",[pp("U13","9"),pp("U13","10"),(22.9,55)],.2)
    bd.via("VIN",22.9,55,.5,.3)
    bd.track(B,"VIN",[pp("C22","2"),(21.8,56.475)],.4)
    bd.via("VIN",21.8,56.475,.6,.3)
    bd.track(I2,"VIN",[(22.9,53.15),(22.9,55),(21.8,56.475)],.4)
    bd.track(I2,"VIN",[(22.9,55),(30,55)],.4)
    bd.track(B,"CAP_USB",[pp("U13","11"),(22.4,54.25),pp("C22","1")],.2)
    bd.track(B,"GND",[pp("U13","5"),(27.35,55.75),(27.7,56.2)],.2)
    bd.via("GND",27.7,56.2,.5,.3)
    for ref,pin,x,y in (("U13","7",22.8,56.9),
                         ("C20","2",17,60.3),("C21","2",31.3,55.95)):
        bd.track(B,"GND",[pp(ref,pin),(x,y)],.2)
        bd.via("GND",x,y,.5,.3)


def build():
    from input_stage import main_power, protection_routes
    bd=Board()
    bd.edge_rect()
    for layer in (F,I1,I2,B):
        bd.rect_zone(layer,"GND",0,0,W,H,priority=0,full=True)
    main_power(bd)
    logic(bd)
    for n in range(1,9):
        channel(bd,n)
    buck_routes(bd)
    usb_routes(bd)
    protection_routes(bd)
    usb_power_routes(bd)
    configure_usb(bd.b)
    for ref,x,y in (("H1",85,52),("H2",3,37.5),("H3",W-3,3.2),("H4",W-3,H-3.5)):
        bd.place(ref,x,y,0,"F")
    bd.text("eswitch rev B",65,69,size=1.2)
    bd.text("2oz / 2oz / 2oz / 2oz",65,72,size=.8)
    for label,x,y,layer,size,rot in fuse_silk_labels():
        bd.text(label,x,y,layer=layer,size=size,rot=rot)
    missing=[r for r in bd.comps if r not in bd.fps]
    assert not missing, missing
    # Dump pad geometry for independent layout review and route construction.
    geometry={ref:[dict(pin=p.GetNumber(),net=p.GetNetname(),x=pcbnew.ToMM(p.GetPosition().x),
                       y=pcbnew.ToMM(p.GetPosition().y),w=pcbnew.ToMM(p.GetSize().x),h=pcbnew.ToMM(p.GetSize().y))
                   for p in fp.Pads() if p.GetNumber()] for ref,fp in bd.fps.items()}
    (Path(ROOT)/"out/revb-pads.json").write_text(json.dumps(geometry,indent=2)+"\n")
    bd.b.GetDesignSettings().SetAuxOrigin(V(0,H))
    sync_metadata(bd.b,NETLIST)
    bd.b.BuildConnectivity()
    pcbnew.ZONE_FILLER(bd.b).Fill(bd.b.Zones())
    save_board(OUT_PCB,bd.b)
    persist_project_rules(OUT_PCB)
    print("Revision B placed:",len(bd.fps),"footprints;",len(list(bd.b.Zones())),"zones")
    return bd


if __name__=="__main__":
    build()
