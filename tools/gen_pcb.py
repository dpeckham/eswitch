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
import design  # noqa: E402

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


def fuse_silk_labels():
    """Circuit identity and maximum fuse size, on the fuse's assembly side."""
    labels = [
        (f"CH{n} MAX FUSE {rating}A", CX[n - 1] + 5.2, 9.4,
         pcbnew.F_SilkS, 0.9, 90)
        for n, (rating, _, _) in design.CHANNELS.items()
    ]
    labels.append(("LOGIC MAX 2A", 20.7, 31.5, pcbnew.B_SilkS, 0.8, 90))
    return labels


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
    ds.m_MinThroughDrill = FromMM(0.254)
    ds.m_CopperEdgeClearance = FromMM(0.4)
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


def persist_project_rules(pcb_path):
    """Persist fabrication constraints, including in headless AppImage sessions.

    KiCad's SaveProject() can return False without writing anything in headless
    Python. Explicitly update these rule keys so later CLI DRC uses the same
    constraints as the zone filler. Preserve all unrelated project settings.
    """
    b = pcbnew.LoadBoard(pcb_path)
    apply_rules(b)
    project = os.path.splitext(pcb_path)[0] + ".kicad_pro"
    with open(project) as f:
        data = json.load(f)
    rules = data["board"]["design_settings"]["rules"]
    ds = b.GetDesignSettings()
    for key, value in {
        "min_clearance": ds.m_MinClearance,
        "min_track_width": ds.m_TrackMinWidth,
        "min_via_diameter": ds.m_ViasMinSize,
        "min_through_hole_diameter": ds.m_MinThroughDrill,
        "min_copper_edge_clearance": ds.m_CopperEdgeClearance,
        "min_hole_clearance": ds.m_HoleClearance,
        "min_hole_to_hole": ds.m_HoleToHoleMin,
    }.items():
        rules[key] = pcbnew.ToMM(value)
    with open(project, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print("project fabrication rules saved")


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
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
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
            if ref in ("J2", "J3"):
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            if ref == "U10" and 0 < pad.GetDrillSize().x < FromMM(0.254):
                pad.SetDrillSize(V(0.254, 0.254))
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
    # +12V bus (1 oz copper): band on F.Cu across all cells; a tall In2.Cu region under cells 1-7
    # (the 20 A CH8 cell keeps In2 free for its own wide VS/OUT copper and is fed by the F.Cu
    # band alone); the stud column carries the full input current on three layers.
    x_bus_end = CX[7] + 7.62
    x_in2_end = CX[6] + 7.62
    bd.rect_zone(pcbnew.F_Cu, "+12V", X_BUS0, Y_BAND[0], x_bus_end, Y_BAND[1], priority=2)
    bd.rect_zone(pcbnew.F_Cu, "+12V", X_BUS0, 3.0, CELL0 - 0.3, 33.0, priority=3)
    # In2 region stops at y=34 so the In2 signal corridor (y 34.5..50) under the cells stays open
    bd.rect_zone(pcbnew.In2_Cu, "+12V", X_BUS0, Y_BAND[0] - 0.5, x_in2_end, 34.0, priority=2)
    bd.rect_zone(pcbnew.In2_Cu, "+12V", X_BUS0, 3.0, CELL0 - 0.3, 33.0, priority=3)
    bd.rect_zone(pcbnew.B_Cu, "+12V", X_BUS0, 3.0, CELL0 - 0.5, 35.0, priority=2)

    # ------------------------------------------------------------- I/O parts (top side THT)
    for i, ref in enumerate(design.OUTPUT_REFS):
        bd.place(ref, CX[i] - 3.81, Y_TERM, 0, "F")
        bd.fps[ref].Reference().SetVisible(False)
    bd.place("J2", STUD_12V[0], STUD_12V[1], 0, "F")
    bd.place("J3", STUD_GND[0], STUD_GND[1], 0, "F")
    for r in ("J1", "J2", "J3"):
        bd.fps[r].Reference().SetVisible(False)
    bd.place("J5", 33.5, 46.5, 0, "F")
    bd.place("H1", 43.0, 30.6, 0, "F")
    bd.place("H2", 3.0, 37.5, 0, "F")
    bd.place("H3", W - 2.5, 3.2, 0, "F")
    bd.place("H4", W - 2.5, H - 3.5, 0, "F")
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
        if n == 8:
            # 20 A channel: parallel copper on In2.Cu for both the fused input and the output,
            # stitched to the B.Cu strips, and a wider output strip toward the board edge.
            bd.zone(pcbnew.In2_Cu, VS, [
                (cx - 7.1, 3.8), (cx + 3.4, 3.8), (cx + 3.4, 16.4), (cx - 3.5, 16.4),
                (cx - 3.5, 22.6), (cx + 1.3, 22.6), (cx + 1.3, 25.7), (cx - 3.5, 25.7),
                (cx - 3.5, 31.8), (cx - 7.1, 31.8)], priority=3, min_th=0.3)
            for vy in (10.0, 13.0, 16.0, 19.0, 22.0, 25.0):
                bd.via(VS, cx - 5.0, vy, 0.9, 0.45)
                bd.via(VS, cx - 6.3, vy, 0.9, 0.45)
            bd.rect_zone(pcbnew.B_Cu, LOAD, cx + 2.0, 27.0, cx + 10.5, 53.8, priority=4, min_th=0.3)
            bd.zone(pcbnew.In2_Cu, LOAD, [
                (cx - 3.1, 26.9), (cx + 10.5, 26.9), (cx + 10.5, 53.8), (cx + 2.0, 53.8),
                (cx + 2.0, 30.3), (cx - 3.1, 30.3)], priority=3, min_th=0.3)
            for vy in (33.0, 37.0, 41.0, 45.0, 49.0):
                bd.via(LOAD, cx + 6.0, vy, 0.9, 0.45)
                bd.via(LOAD, cx + 8.8, vy, 0.9, 0.45)
        # silkscreen
        rating = design.CHANNELS[n][0]
        bd.text(f"CH{n}", cx, 43.8, size=1.2)
        bd.text("+", cx + 3.81, 46.0, size=1.2, thick=0.25)
        bd.text("-", cx - 3.81, 46.0, size=1.2, thick=0.25)
        bd.text(f"CH{n}", cx + 5.0, 12.0, layer=pcbnew.B_SilkS, size=1.0, rot=90)

    # ------------------------------------------------------------- ESP32 / power section (bottom)
    bd.place("U10", 12.0, 8.6, 0, "B")
    bd.place("C10", 23.4, 2.0, 0, "B")      # 100 nF right at the module's 3V3 pin
    bd.place("C9", 24.0, 12.7, 90, "B")     # 10 uF, below the IS pin group
    bd.place("R5", 9.0, 30.0, 0, "B")       # EN pull-up
    bd.place("C11", 12.0, 30.0, 0, "B")     # EN cap
    bd.place("R6", 15.0, 30.0, 0, "B")      # IO0 pull-up
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
    bd.place("U11", 14.5, 42.0, 0, "B")
    # CC pull-downs sit in line with the CC1/CC2 escape stubs (pad 1 on the stub end)
    bd.place("R7", 11.9, 52.75, 0, "B")
    bd.place("R8", 11.9, 49.75, 0, "B")
    for r in ("R7", "R8"):
        f = bd.fps[r]
        pads = {p.GetNumber(): p.GetPosition() for p in f.Pads()}
        if pads["1"].x > pads["2"].x:
            pos = f.GetPosition()
            f.SetOrientationDegrees(f.GetOrientationDegrees() + 180)
            f.SetPosition(pos)

    bd.text("USB", 5.0, 44.5, layer=pcbnew.B_SilkS, size=1.0)
    bd.text("RESET", 12.5, 25.2, size=0.8)
    bd.text("BOOT", 12.5, 43.0, size=0.9)
    bd.text("G 3 T R", 30.5, 46.5, size=0.8, rot=90)
    for label, x, y, layer, size, rot in fuse_silk_labels():
        bd.text(label, x, y, layer=layer, size=size, rot=rot)

    # +12V feed for the logic fuse: B.Cu track from F9 pad 1 into the +12V patch under the stud
    for ref in ("F9", "D3"):
        px, py = bd.pad_pos(ref, "1")
        bd.track(pcbnew.B_Cu, "+12V", [(px, py), (37.5, py)], 0.6)
    # USB-C pad row (0.5 mm pitch): D+ (A6,B6) and D- (A7,B7) interleave, so tie D+ behind the
    # row (connector-body side) and D- in front (inboard); VBUS pads A4/A9 are joined on In2.Cu.
    fp = bd.fps["J4"]
    c = fp.GetPosition()
    P = {n: bd.pad_pos("J4", n) for n in ("A4", "A9", "A5", "B5", "A6", "A7", "B6", "B7")}
    mx, my = (P["A4"][0] + P["A9"][0]) / 2, (P["A4"][1] + P["A9"][1]) / 2
    dx, dy = mx - pcbnew.ToMM(c.x), my - pcbnew.ToMM(c.y)
    L = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / L, dy / L                      # unit vector from the row toward the board interior

    def off(pt, d):
        return (pt[0] + ux * d, pt[1] + uy * d)
    B = pcbnew.B_Cu
    bd.track(B, "USB_D+", [P["A6"], off(P["A6"], -1.0), off(P["B6"], -1.0), P["B6"]], 0.25)
    bd.track(B, "USB_D+", [P["B6"], off(P["B6"], 2.2)], 0.25)
    bd.track(B, "USB_D-", [P["A7"], off(P["A7"], 1.0), off(P["B7"], 1.0), P["B7"]], 0.25)
    m7 = ((P["A7"][0] + P["B7"][0]) / 2, (P["A7"][1] + P["B7"][1]) / 2)
    bd.track(B, "USB_D-", [off(m7, 1.0), off(m7, 2.2)], 0.25)
    bd.track(B, "CC1", [P["A5"], off(P["A5"], 2.2)], 0.25)
    bd.track(B, "CC2", [P["B5"], off(P["B5"], 2.2)], 0.25)
    # VBUS: tie A4/A9 on the body side (dog-leg around the alignment pegs), one inboard stub
    rx, ry = (P["A4"][0] - P["A9"][0]), (P["A4"][1] - P["A9"][1])
    Lr = (rx * rx + ry * ry) ** 0.5
    rx, ry = rx / Lr, ry / Lr                      # unit vector along the row from A9 to A4
    def rowpt(pad, t, r):
        """Point t mm on the body side of pad `pad` and r mm along the row (toward A4)."""
        x, y = P[pad]
        return (x - ux * t + rx * r, y - uy * t + ry * r)
    bd.track(B, "VBUS", [P["A4"], rowpt("A4", 0.55, 0), rowpt("A4", 1.75, -0.6),
                         rowpt("A9", 1.75, 0.6), rowpt("A9", 0.55, 0), P["A9"]], 0.3)
    bd.track(B, "VBUS", [P["A4"], off(P["A4"], 2.2)], 0.3)
    # placement/drill origin at the board's bottom-left corner so vendor CPL coordinates are positive
    b.GetDesignSettings().SetAuxOrigin(V(0, H))
    b.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    nf = sum(1 for z in b.Zones() if z.IsFilled())
    print("zones filled:", nf, "/", len(list(b.Zones())))
    pcbnew.SaveBoard(OUT_PCB, b)
    persist_project_rules(OUT_PCB)
    print("wrote", OUT_PCB, "footprints:", len(list(b.GetFootprints())), "zones:", len(list(b.Zones())))
    missing = [r for r in bd.comps if r not in bd.fps]
    if missing:
        print("NOT PLACED:", missing)
    return bd


if __name__ == "__main__":
    build()
