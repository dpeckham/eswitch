#!/usr/bin/env python3
"""Post-route clean-up: drop dangling auto-router leftovers, apply manual fix-up routes, refill."""
import os
import sys
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from gen_pcb import apply_rules, persist_project_rules  # noqa: E402

PCB = os.path.join(ROOT, "eswitch.kicad_pcb")
FromMM = pcbnew.FromMM
ZONE_NETS = ("GND", "+12V", "VS", "LOAD")

# Manual fix-ups (net, layer, points, width) and vias (net, x, y, dia, drill) for nets the
# router could not finish. Coordinates in mm on the final placement.
TRACKS = [
    ("CC2", pcbnew.B_Cu, [(8.68, 49.75), (10.6, 49.75)], 0.25),
    ("CC2", pcbnew.F_Cu, [(10.6, 49.75), (15.5, 50.5)], 0.25),
    ("CC2", pcbnew.B_Cu, [(15.5, 50.5), (15.5, 51.67)], 0.25),
    # GND island of C3: via spot chosen automatically near the pad (see AUTO_VIAS)
]
AUTO_VIAS = [
    # (net, pad ref, pad number, search box (x1, y1, x2, y2), via dia, drill)
    ("GND", "C3", "2", (34.3, 8.9, 35.55, 10.9), 0.5, 0.3),
]
VIAS = [
    ("CC2", 10.6, 49.75, 0.6, 0.3),
    ("CC2", 15.5, 50.5, 0.6, 0.3),
]


def V(x, y):
    return pcbnew.VECTOR2I(FromMM(x), FromMM(y))


def is_zone_net(name):
    return name.startswith(ZONE_NETS)


def prune_dangling(b):
    """Remove auto-routed track segments / vias with a free end (signal nets only)."""
    removed = 0
    if True:
        alltracks = list(b.Tracks())
        tracks = [t for t in alltracks if t.GetClass() == "PCB_TRACK" and not is_zone_net(t.GetNetname())]
        vias = [t for t in alltracks if t.GetClass() == "PCB_VIA"]
        pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
        ends = {}
        for t in alltracks:
            if t.GetClass() != "PCB_TRACK":
                continue
            for e in (t.GetStart(), t.GetEnd()):
                ends.setdefault((e.x, e.y, t.GetNetCode()), []).append(t)
        via_pos = {(v.GetPosition().x, v.GetPosition().y, v.GetNetCode()) for v in vias}

        def attached(t, e):
            key = (e.x, e.y, t.GetNetCode())
            if len(ends.get(key, [])) > 1 or key in via_pos:
                return True
            for p in pads:
                if p.GetNetCode() == t.GetNetCode() and p.HitTest(e):
                    return True
            for o in alltracks:
                if o is not t and o.GetClass() == "PCB_TRACK" and o.GetNetCode() == t.GetNetCode() \
                        and o.GetLayer() == t.GetLayer() and o.HitTest(e, FromMM(0.01)):
                    return True
            return False
        victims = [t for t in tracks if not (attached(t, t.GetStart()) and attached(t, t.GetEnd()))]
        for v in vias:
            if is_zone_net(v.GetNetname()):
                continue
            layers = set()
            for t in alltracks:
                if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == v.GetNetCode() and \
                        (t.GetStart() == v.GetPosition() or t.GetEnd() == v.GetPosition()):
                    layers.add(t.GetLayer())
            if len(layers) < 2:
                victims.append(v)
        for t in victims:
            b.Remove(t)
        removed += len(victims)
    print("dangling items removed:", removed)
    return removed


def find_via_spot(b, net, box, dia):
    """Point in `box` (mm) farthest from copper of other nets on any layer (tracks, vias, pads, zones)."""
    x1, y1, x2, y2 = box
    net_code = b.FindNet(net).GetNetCode()
    items = []
    for t in b.Tracks():
        if t.GetNetCode() != net_code:
            items.append(t)
    pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetCode() != net_code]
    zones = [z for z in b.Zones() if z.GetNetCode() != net_code and not z.GetIsRuleArea()]
    best, bestd = None, -1
    step = 0.1
    y = y1
    while y <= y2 + 1e-9:
        x = x1
        while x <= x2 + 1e-9:
            pt = pcbnew.VECTOR2I(FromMM(x), FromMM(y))
            d = 1e12
            for t in items:
                if t.GetClass() == "PCB_VIA":
                    d = min(d, (t.GetPosition() - pt).EuclideanNorm() - t.GetWidth(t.GetLayer()) // 2)
                else:
                    d = min(d, pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(pt) - t.GetWidth() // 2)
            for p in pads:
                d = min(d, (p.GetPosition() - pt).EuclideanNorm() - max(p.GetSize().x, p.GetSize().y) // 2)
            for z in zones:
                for li in range(4):
                    layer = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu][li]
                    if not z.IsOnLayer(layer):
                        continue
                    fp_ = z.GetFilledPolysList(layer)
                    if fp_.OutlineCount():
                        if fp_.Contains(pt):
                            d = -1
                        else:
                            d = min(d, fp_.Distance(pt) if hasattr(fp_, "Distance") else d)
            if d > bestd:
                best, bestd = (x, y), d
            x += step
        y += step
    need = FromMM(dia / 2 + 0.2)
    print(f"via spot for {net}: {best} clearance {pcbnew.ToMM(int(bestd)) if bestd > 0 else bestd:.2f} mm (need {pcbnew.ToMM(need):.2f})")
    return best if bestd >= need else None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "fix"
    b = pcbnew.LoadBoard(PCB)
    apply_rules(b)
    if mode == "prune":
        # one pass per process: the SWIG track container cannot be re-iterated after removals
        n = prune_dangling(b)
        pcbnew.SaveBoard(PCB, b)
        sys.exit(1 if n else 0)
    for net, layer, pts, w in TRACKS:
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(V(x1, y1))
            t.SetEnd(V(x2, y2))
            t.SetWidth(FromMM(w))
            t.SetLayer(layer)
            t.SetNet(b.FindNet(net))
            b.Add(t)
    for net, x, y, dia, drill in VIAS:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(V(x, y))
        v.SetDrill(FromMM(drill))
        v.SetWidth(FromMM(dia))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(b.FindNet(net))
        b.Add(v)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    for net, ref, num, box, dia, drill in AUTO_VIAS:
        pad = [p for fp in b.GetFootprints() if fp.GetReference() == ref for p in fp.Pads() if p.GetNumber() == num][0]
        spot = find_via_spot(b, net, box, dia)
        if spot is None:
            print("no via spot found for", ref, num)
            continue
        pp = pad.GetPosition()
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pp)
        t.SetEnd(V(*spot))
        t.SetWidth(FromMM(0.3))
        t.SetLayer(pad.GetLayer())
        t.SetNet(pad.GetNet())
        b.Add(t)
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(V(*spot))
        v.SetDrill(FromMM(drill))
        v.SetWidth(FromMM(dia))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(pad.GetNet())
        b.Add(v)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
    persist_project_rules(PCB)
    print("saved", PCB)


if __name__ == "__main__":
    main()
