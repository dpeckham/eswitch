#!/usr/bin/env python3
"""Generate eswitch.kicad_pcb from the exported netlist (run with KiCad's python: `kicad python3.11`).

Board concept (all dimensions mm, origin = board top-left, Y down):
  * 4 layers: F.Cu (hand-solder THT side: fuse clips, terminal block, screw terminals, header),
    In1.Cu = solid GND plane, In2.Cu = +12V bus region under the fuse area + GND elsewhere,
    B.Cu = all SMD parts (PROFETs, ESP32-S3, buck).
  * 8 identical channel cells, 15.24 mm pitch, each holding a 3-clip ATO fuse column on top and the
    PROFET plus its passives on the bottom. Power copper per cell is drawn explicitly as zones.
  * Signal nets are auto-routed by freerouting (tools/route.py) after this script runs.
"""
import os
import sys
import json

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexp import parse_one, find, find_all  # noqa: E402
import kicad_env  # noqa: E402

NETLIST = os.path.join(ROOT, "out", "eswitch.net")
OUT_PCB = os.path.join(ROOT, "eswitch.kicad_pcb")

FromMM = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(FromMM(x), FromMM(y))


# --------------------------------------------------------------------------- geometry
W, H = 181.0, 57.5              # board outline
PITCH = 15.24
CELL0 = 51.0                    # left edge of cell 0
CX = [CELL0 + PITCH / 2 + i * PITCH for i in range(8)]   # cell centres
Y_FUSE = 17.5                   # fuse holder origin (COM blade) y
Y_BAND = (8.0, 27.0)            # +12V bus band on F.Cu / In2.Cu
Y_TERM = 52.3                   # terminal block pin row
Y_BTS = 35.0                    # PROFET centre
X_BUS0 = 36.0                   # left end of the bus band / stud column
STUD_12V = (43.0, 17.3)
STUD_GND = (43.0, 44.0)

# --------------------------------------------------------------------------- netlist
def read_netlist(path):
    doc = parse_one(open(path).read())
    comps = {}
    for c in find_all(find(doc, "components"), "comp"):
        ref = find(c, "ref")[1]
        comps[ref] = {"value": find(c, "value")[1], "footprint": find(c, "footprint")[1]}
    nets = {}
    for net in find_all(find(doc, "nets"), "net"):
        name = find(net, "name")[1].lstrip("/")
        nets[name] = [(find(n, "ref")[1], str(find(n, "pin")[1])) for n in find_all(net, "node")]
    return comps, nets


def apply_rules(b):
    """Design constraints and net classes (must be re-applied after LoadBoard: classes live in the project)."""
    ds = b.GetDesignSettings()
    ds.m_MinClearance = FromMM(0.2)
    ds.m_TrackMinWidth = FromMM(0.15)
    ds.m_ViasMinSize = FromMM(0.5)
    ds.m_MinThroughDrill = FromMM(0.2)
    ds.m_CopperEdgeClearance = FromMM(0.3)
    ds.m_HoleClearance = FromMM(0.15)
    ds.m_HoleToHoleMin = FromMM(0.25)
    ns = ds.m_NetSettings
    dflt = ns.GetDefaultNetclass()
    dflt.SetTrackWidth(FromMM(0.25))
    dflt.SetClearance(FromMM(0.2))
    dflt.SetViaDiameter(FromMM(0.7))
    dflt.SetViaDrill(FromMM(0.35))
    pwr = pcbnew.NETCLASS("Power")
    pwr.SetTrackWidth(FromMM(0.6))
    pwr.SetClearance(FromMM(0.2))
    pwr.SetViaDiameter(FromMM(0.9))
    pwr.SetViaDrill(FromMM(0.45))
    ns.SetNetclass("Power", pwr)
    for pat in ["+3V3", "VIN", "SW", "V12F", "+12V", "GND"]:
        ns.SetNetclassPatternAssignment(pat, "Power")


class Board:
    def __init__(self):
        self.b = pcbnew.BOARD()
        b = self.b
        b.SetCopperLayerCount(4)
        b.SetLayerName(pcbnew.In1_Cu, "GND")
        b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
        b.SetLayerName(pcbnew.In2_Cu, "PWR")
        apply_rules(b)
        self.nets = {}
        self.comps, self.netlist = read_netlist(NETLIST)
        for name in self.netlist:
            ni = pcbnew.NETINFO_ITEM(b, name)
            b.Add(ni)
            self.nets[name] = ni
        self.pad_net = {}
        for name, nodes in self.netlist.items():
            for ref, pin in nodes:
                self.pad_net[(ref, pin)] = name
        self.fps = {}

    # ----------------------------------------------------------------- footprints
    def load_fp(self, fpid):
        lib, name = fpid.split(":", 1)
        if lib == "eswitch":
            path = os.path.join(ROOT, "lib", "eswitch.pretty")
        else:
            path = kicad_env.footprint_lib_dir(lib)
        fp = pcbnew.FootprintLoad(path, name)
        if fp is None:
            raise RuntimeError(f"footprint not found: {fpid}")
        return fp

    def place(self, ref, x, y, rot=0, side="B"):
        c = self.comps[ref]
        fp = self.load_fp(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        if ref == "U10":
            # replace the huge antenna-keepout courtyard / rule area with the module body outline
            for it in list(fp.GraphicalItems()):
                if it.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd) or it.GetLayer() == pcbnew.Cmts_User:
                    fp.Remove(it)
            for z in list(fp.Zones()):
                fp.Remove(z)
            r = pcbnew.PCB_SHAPE(fp)
            r.SetShape(pcbnew.SHAPE_T_RECT)
            r.SetStart(V(-9.3, -13.05))
            r.SetEnd(V(9.3, 13.05))
            r.SetLayer(pcbnew.F_CrtYd)
            r.SetWidth(FromMM(0.05))
            fp.Add(r)
        for pad in fp.Pads():
            net = self.pad_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(self.nets[net])
        self.b.Add(fp)
        fp.SetPosition(V(0, 0))
        if side == "B":
            fp.Flip(V(0, 0), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        # rotation is applied relative to whatever orientation Flip() left behind
        fp.SetOrientationDegrees(fp.GetOrientationDegrees() + rot)
        fp.SetPosition(V(x, y))
        self.fps[ref] = fp
        if ref[0] in "RCDLF" and ref not in ("L1",) and ("0603" in c["footprint"] or "0805" in c["footprint"] or "SOT-23" in c["footprint"]):
            fp.Reference().SetVisible(False)
        return fp

    def pin_up(self, ref, num="1"):
        """Rotate a 2-pad part by 180 deg if pad `num` is not the upper pad."""
        fp = self.fps[ref]
        pads = {p.GetNumber(): p.GetPosition() for p in fp.Pads()}
        other = [k for k in pads if k != num][0]
        if pads[num].y > pads[other].y:
            pos = fp.GetPosition()
            fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)
            fp.SetPosition(pos)

    def pad_pos(self, ref, num):
        for pad in self.fps[ref].Pads():
            if pad.GetNumber() == num:
                p = pad.GetPosition()
                return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        raise KeyError((ref, num))

    # ----------------------------------------------------------------- copper
    def zone(self, layer, net, pts, priority=0, full=True, min_th=0.25, clearance=0.25):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(layer)
        z.SetNet(self.nets[net])
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(x, y) for x, y in pts]))
        z.SetAssignedPriority(priority)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if full else pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetMinThickness(FromMM(min_th))
        z.SetLocalClearance(FromMM(clearance))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetZoneName(f"{net}_{pcbnew.BOARD.GetStandardLayerName(layer)}_{len(list(self.b.Zones()))}")
        self.b.Add(z)
        return z

    def rect_zone(self, layer, net, x1, y1, x2, y2, **kw):
        return self.zone(layer, net, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], **kw)

    def track(self, layer, net, pts, width):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(V(x1, y1))
            t.SetEnd(V(x2, y2))
            t.SetWidth(FromMM(width))
            t.SetLayer(layer)
            t.SetNet(self.nets[net])
            self.b.Add(t)

    def via(self, net, x, y, dia=0.8, drill=0.4):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(V(x, y))
        v.SetDrill(FromMM(drill))
        v.SetWidth(FromMM(dia))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.nets[net])
        self.b.Add(v)

    def stitch_gnd_pads(self):
        """Give every SMD GND pad its own via to the inner GND plane (short stub + via)."""
        n = 0
        for fp in self.b.GetFootprints():
            if fp.GetReference() == "U10":
                continue  # module GND pads: the big centre pad already carries thermal vias
            c = fp.GetPosition()
            for pad in fp.Pads():
                if pad.GetNetname() != "GND" or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                    continue
                p = pad.GetPosition()
                dx, dy = pcbnew.ToMM(p.x - c.x), pcbnew.ToMM(p.y - c.y)
                L = (dx * dx + dy * dy) ** 0.5
                if L < 0.1:
                    dx, dy, L = 0.0, 1.0, 1.0
                ux, uy = dx / L, dy / L
                off = 0.95 + max(pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)) / 2
                vx, vy = pcbnew.ToMM(p.x) + ux * off, pcbnew.ToMM(p.y) + uy * off
                self.track(pcbnew.B_Cu if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_Cu, "GND",
                           [(pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)), (vx, vy)], 0.3)
                self.via("GND", vx, vy, 0.7, 0.35)
                n += 1
        print("GND stitch vias:", n)

    # ----------------------------------------------------------------- graphics
    def edge_rect(self):
        for (x1, y1), (x2, y2) in [((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))]:
            s = pcbnew.PCB_SHAPE(self.b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(V(x1, y1))
            s.SetEnd(V(x2, y2))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(FromMM(0.1))
            self.b.Add(s)

    def text(self, s, x, y, layer=pcbnew.F_SilkS, size=1.0, rot=0, thick=0.15):
        t = pcbnew.PCB_TEXT(self.b)
        t.SetText(s)
        t.SetPosition(V(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(thick))
        t.SetTextAngleDegrees(rot)
        if layer in (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Fab):
            t.SetMirrored(True)
        self.b.Add(t)

    def line(self, x1, y1, x2, y2, layer=pcbnew.F_SilkS, w=0.15):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(x1, y1))
        s.SetEnd(V(x2, y2))
        s.SetLayer(layer)
        s.SetWidth(FromMM(w))
        self.b.Add(s)


def build():
    bd = Board()
    b = bd.b
    bd.edge_rect()

    # ------------------------------------------------------------- global copper
    bd.rect_zone(pcbnew.In1_Cu, "GND", 0, 0, W, H, priority=0, full=True)
    bd.rect_zone(pcbnew.In2_Cu, "GND", 0, 0, W, H, priority=0, full=True)
    zf = bd.rect_zone(pcbnew.F_Cu, "GND", 0, 0, W, H, priority=0, full=False)
    zb = bd.rect_zone(pcbnew.B_Cu, "GND", 0, 0, W, H, priority=0, full=False)
    zf.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
    zb.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
    # +12V bus: band on F.Cu, wide region on In2.Cu, small B.Cu patch under the 12V stud
    x_bus_end = CX[7] + 7.62
    bd.rect_zone(pcbnew.F_Cu, "+12V", X_BUS0, Y_BAND[0], x_bus_end, Y_BAND[1], priority=2)
    bd.rect_zone(pcbnew.In2_Cu, "+12V", X_BUS0, Y_BAND[0] - 0.5, x_bus_end, Y_BAND[1] + 0.3, priority=2)
    bd.rect_zone(pcbnew.B_Cu, "+12V", X_BUS0, Y_BAND[0], CELL0 - 0.5, 35.0, priority=2)

    # ------------------------------------------------------------- I/O parts (top side THT)
    bd.place("J1", CX[0] - 3.81, Y_TERM, 0, "F")
    bd.place("J2", STUD_12V[0], STUD_12V[1], 0, "F")
    bd.place("J3", STUD_GND[0], STUD_GND[1], 0, "F")
    for r in ("J1", "J2", "J3"):
        bd.fps[r].Reference().SetVisible(False)
    bd.place("J5", 33.5, 46.5, 0, "F")
    bd.place("H1", 43.0, 30.6, 0, "F")
    bd.place("H2", 3.0, 37.5, 0, "F")
    bd.place("H3", W - 3.2, 3.2, 0, "F")
    bd.place("H4", W - 3.2, H - 3.5, 0, "F")
    bd.text("+12V IN", STUD_12V[0], STUD_12V[1] - 8.6, size=1.2)
    bd.text("GND IN", STUD_GND[0], STUD_GND[1] - 8.6, size=1.2)
    bd.text("eswitch rev A", 20.0, 44.0, size=1.0, rot=90)
    bd.text("eswitch rev A - SMD side", 110.0, 55.9, layer=pcbnew.B_SilkS, size=1.0)

    # ------------------------------------------------------------- channels
    for n in range(1, 9):
        cx = CX[n - 1]
        i = n
        bd.place(f"F{n}", cx, Y_FUSE, 0, "F")
        u = bd.place(f"U{n}", cx, Y_BTS, 0, "B")
        # orient so OUT pins (8..14) sit on the +x side and pins 1..4 at the bottom-left
        p1 = bd.pad_pos(f"U{n}", "1")
        p8 = bd.pad_pos(f"U{n}", "8")
        if p8[0] < p1[0]:
            u.SetOrientationDegrees(180)
            u.SetPosition(V(cx, Y_BTS))
        p1 = bd.pad_pos(f"U{n}", "1")
        if p1[1] < Y_BTS:  # want pin 1 (GND) toward the bottom
            u.SetOrientationDegrees(u.GetOrientationDegrees() + 180)
            u.SetPosition(V(cx, Y_BTS))
        # bottom-side passives (3.2 mm row pitch keeps 0603 courtyards apart)
        bd.place(f"C{i}01", cx - 6.0, 34.6, 90, "B"); bd.pin_up(f"C{i}01")     # CVS, pad 1 (VS) up
        bd.place(f"R{i}03", cx - 6.2, 39.6, 90, "B")            # RGND
        bd.place(f"R{i}04", cx - 6.2, 42.8, 90, "B")            # RSENSE
        bd.place(f"R{i}05", cx - 6.2, 46.0, 90, "B")            # RADC
        bd.place(f"C{i}03", cx - 6.2, 49.2, 90, "B")            # CSENSE
        bd.place(f"R{i}01", cx - 3.8, 39.6, 90, "B")            # RIN
        bd.place(f"R{i}02", cx - 3.8, 42.8, 90, "B")            # RDEN
        bd.place(f"D{i}01", cx - 2.6, 47.6, 0, "B")             # BAT54S clamp
        bd.place(f"C{i}02", cx + 0.2, 40.6, 90, "B")            # COUT
        bd.place(f"R{i}06", cx + 0.2, 44.2, 90, "B")            # RPD
        bd.place(f"R{i}07", cx + 5.3, 19.0, 90, "B"); bd.pin_up(f"R{i}07")     # RLED, pad 1 (LOAD) up
        bd.place(f"D{i}02", cx + 5.3, 23.4, 90, "B"); bd.pin_up(f"D{i}02", "2")  # LED anode up (to RLED)
        VS, LOAD = f"VS{n}", f"LOAD{n}"
        # VS copper (B.Cu): clip-1 pads -> left strip -> connector -> PROFET exposed pad
        bd.zone(pcbnew.B_Cu, VS, [
            (cx - 7.1, 3.8), (cx + 3.4, 3.8), (cx + 3.4, 8.2), (cx - 3.5, 8.2),
            (cx - 3.5, 30.8), (cx + 1.3, 30.8), (cx + 1.3, 33.4),
            (cx - 1.3, 33.4), (cx - 1.3, 31.8), (cx - 7.1, 31.8)], priority=3, min_th=0.3)
        # thermal pad tab below the EP and F.Cu cooling patch stitched with vias
        bd.rect_zone(pcbnew.B_Cu, VS, cx - 1.3, 36.6, cx + 1.3, 38.6, priority=3)
        bd.rect_zone(pcbnew.F_Cu, VS, cx - 7.1, 27.6, cx - 3.5, 34.0, priority=3)
        for vy in (28.6, 30.4):
            bd.via(VS, cx - 5.0, vy, 0.9, 0.45)
            bd.via(VS, cx - 6.3, vy, 0.9, 0.45)
        # OUT / LOAD copper (B.Cu): clip-3 pads -> right strip -> terminal '+' pin
        bd.zone(pcbnew.B_Cu, LOAD, [
            (cx - 3.3, 26.9), (cx + 7.1, 26.9), (cx + 7.1, 53.8), (cx + 2.0, 53.8),
            (cx + 2.0, 30.3), (cx - 3.3, 30.3)], priority=3, min_th=0.3)
        # explicit stubs from LOAD-net passives into the OUT strip
        for ref, num in ((f"C{i}02", "1"), (f"R{i}06", "1")):
            px, py = bd.pad_pos(ref, num)
            bd.track(pcbnew.B_Cu, LOAD, [(px, py), (cx + 2.6, py)], 0.5)
        px, py = bd.pad_pos(f"R{i}07", "1")
        bd.track(pcbnew.B_Cu, LOAD, [(px, py), (px, 16.6), (cx + 3.9, 16.6), (cx + 3.9, 28.5)], 0.5)
        # CVS pad 1 -> VS connector
        px, py = bd.pad_pos(f"C{i}01", "1")
        bd.track(pcbnew.B_Cu, VS, [(px, py), (px, 31.3)], 0.5)
        # silkscreen
        bd.text(f"CH{n}", cx, 47.0, size=1.5)
        bd.text("+", cx + 3.81, 49.3, size=1.2, thick=0.25)
        bd.text("-", cx - 3.81, 49.3, size=1.2, thick=0.25)
        bd.text(f"CH{n}", cx + 5.0, 12.0, layer=pcbnew.B_SilkS, size=1.0, rot=90)

    # ------------------------------------------------------------- ESP32 / power section (bottom)
    bd.place("U10", 12.0, 8.6, 0, "B")
    bd.place("C10", 24.0, 6.0, 90, "B")
    bd.place("C9", 24.0, 9.5, 90, "B")
    bd.place("R5", 24.0, 12.7, 90, "B")
    bd.place("C11", 24.0, 15.9, 90, "B")
    bd.place("R6", 24.0, 19.1, 90, "B")
    bd.place("D5", 5.0, 25.0, 0, "B")
    bd.place("R9", 8.5, 25.0, 0, "B")
    bd.place("SW1", 12.5, 30.0, 0, "F")
    bd.place("SW2", 12.5, 38.5, 0, "F")
    # buck
    bd.place("C1", 28.5, 3.0, 0, "B")
    bd.place("C2", 33.5, 3.0, 0, "B")
    bd.place("U9", 29.8, 9.0, 0, "B")
    bd.place("C3", 34.8, 9.0, 90, "B")
    bd.place("C4", 34.8, 12.5, 90, "B")
    bd.place("R1", 34.8, 15.7, 90, "B")
    bd.place("L1", 29.5, 16.0, 0, "B")
    bd.place("D4", 24.5, 24.5, 90, "B")
    bd.place("C7", 29.5, 22.5, 0, "B")
    bd.place("C8", 29.5, 26.0, 0, "B")
    bd.place("R4", 33.5, 22.3, 90, "B")
    bd.place("C5", 33.5, 25.5, 90, "B")
    bd.place("C6", 33.5, 28.7, 90, "B")
    bd.place("R2", 28.0, 29.5, 0, "B")
    bd.place("R3", 31.0, 29.5, 0, "B")
    # 12V logic feed + TVS
    bd.place("F9", 24.5, 31.5, 0, "B")
    bd.place("D1", 24.5, 35.0, 0, "B")
    bd.place("D2", 24.5, 39.0, 0, "B")
    bd.place("D3", 32.0, 33.5, 0, "B")
    # USB
    j4 = bd.place("J4", 5.0, 51.5, 270, "B")
    # receptacle opening must face the left board edge: the SMD pad row sits at the rear (inboard)
    assert bd.pad_pos("J4", "A4")[0] > 5.0, "J4 orientation: pad row must be inboard of the connector centre"
    bd.place("U11", 14.0, 47.5, 0, "B")
    bd.place("R7", 13.0, 52.5, 90, "B")
    bd.place("R8", 15.5, 52.5, 90, "B")

    bd.text("USB", 5.0, 44.5, layer=pcbnew.B_SilkS, size=1.0)
    bd.text("RESET", 12.5, 25.2, size=0.8)
    bd.text("BOOT", 12.5, 43.0, size=0.9)
    bd.text("G 3 T R", 30.5, 46.5, size=0.8, rot=90)

    # +12V feed for the logic fuse: B.Cu track from F9 pad 1 into the +12V patch under the stud
    for ref in ("F9", "D3"):
        px, py = bd.pad_pos(ref, "1")
        bd.track(pcbnew.B_Cu, "+12V", [(px, py), (37.5, py)], 0.6)
    # USB-C: bridge the two VBUS pad pairs behind the pad row (router cannot fit between pads)
    fp = bd.fps["J4"]
    c = fp.GetPosition()
    p4, p9 = bd.pad_pos("J4", "A4"), bd.pad_pos("J4", "A9")
    mx, my = (p4[0] + p9[0]) / 2, (p4[1] + p9[1]) / 2
    dx, dy = mx - pcbnew.ToMM(c.x), my - pcbnew.ToMM(c.y)
    L = (dx * dx + dy * dy) ** 0.5
    dx, dy = dx / L * 1.3, dy / L * 1.3
    bd.track(pcbnew.B_Cu, "VBUS", [p4, (p4[0] + dx, p4[1] + dy), (p9[0] + dx, p9[1] + dy), p9], 0.3)
    b.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    nf = sum(1 for z in b.Zones() if z.IsFilled())
    print("zones filled:", nf, "/", len(list(b.Zones())))
    pcbnew.SaveBoard(OUT_PCB, b)
    print("wrote", OUT_PCB, "footprints:", len(list(b.GetFootprints())), "zones:", len(list(b.Zones())))
    missing = [r for r in bd.comps if r not in bd.fps]
    if missing:
        print("NOT PLACED:", missing)
    return bd


if __name__ == "__main__":
    build()
