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
    # GND island of C3: via spot chosen automatically near the pad (see AUTO_VIAS)
]
AUTO_VIAS = [
    # (net, pad ref, pad number, search box (x1, y1, x2, y2), via dia, drill)
    ("GND", "C3", "2", (34.3, 8.9, 35.55, 10.9), 0.5, 0.3),
]
VIAS = []


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
        # duplicate vias (same net, nearly co-located) -> keep one
        seen = []
        for v in vias:
            pv = v.GetPosition()
            if any(o.GetNetCode() == v.GetNetCode() and (o.GetPosition() - pv).EuclideanNorm() < FromMM(0.5) for o in seen):
                victims.append(v)
            else:
                seen.append(v)
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
    allvias = []
    for t in b.Tracks():
        if t.GetClass() == "PCB_VIA":
            allvias.append(t.GetPosition())
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
                half_diag = int(((p.GetSize().x ** 2 + p.GetSize().y ** 2) ** 0.5) / 2)
                d = min(d, (p.GetPosition() - pt).EuclideanNorm() - half_diag)
            for v in allvias:  # hole-to-hole spacing to any via
                d = min(d, (v - pt).EuclideanNorm() - FromMM(0.6))
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


if __name__ == "__main__" and not (len(sys.argv) > 1 and sys.argv[1] in ("manual", "manual2")):
    main()


# ----------------------------------------------------------------------------- lane router
CLR = 0.2


def _clear_point(b, net_code, pt, radius):
    """True if a via of `radius` at pt clears all other-net copper on every layer and other holes."""
    need = FromMM(radius + CLR)
    for t in b.Tracks():
        if t.GetClass() == "PCB_VIA":
            d = (t.GetPosition() - pt).EuclideanNorm()
            if d < FromMM(radius + 0.35 + 0.3):  # hole-to-hole spacing for any via
                return False
            if t.GetNetCode() != net_code and d < need + t.GetWidth(t.GetLayer()) // 2:
                return False
        elif t.GetNetCode() != net_code:
            if pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(pt) < need + t.GetWidth() // 2:
                return False
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == net_code and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                continue
            d = (p.GetPosition() - pt).EuclideanNorm() - int((p.GetSize().x ** 2 + p.GetSize().y ** 2) ** 0.5 / 2)
            if d < need or (p.GetDrillSize().x and (p.GetPosition() - pt).EuclideanNorm() < FromMM(radius) + p.GetDrillSize().x // 2 + FromMM(0.3)):
                return False
    bb = b.GetBoardEdgesBoundingBox()
    if pt.x - need < bb.GetLeft() + FromMM(0.3) or pt.x + need > bb.GetRight() - FromMM(0.3) or \
            pt.y - need < bb.GetTop() + FromMM(0.3) or pt.y + need > bb.GetBottom() - FromMM(0.3):
        return False
    return True


def _clear_segment(b, net_code, layer, p1, p2, width):
    """True if a track p1-p2 of `width` on `layer` clears all other-net copper on that layer."""
    seg = pcbnew.SEG(p1, p2)
    need = FromMM(width / 2 + CLR)
    for t in b.Tracks():
        if t.GetNetCode() == net_code:
            continue
        if t.GetClass() == "PCB_VIA":
            if seg.Distance(t.GetPosition()) < need + t.GetWidth(t.GetLayer()) // 2:
                return False
        elif t.GetLayer() == layer:
            if seg.Distance(pcbnew.SEG(t.GetStart(), t.GetEnd())) < need + t.GetWidth() // 2:
                return False
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == net_code or not p.IsOnLayer(layer):
                continue
            if seg.Distance(p.GetPosition()) < need + max(p.GetSize().x, p.GetSize().y) // 2:
                return False
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() == net_code or z.GetNetname() == "GND" or not z.IsOnLayer(layer):
            continue
        polys = z.GetFilledPolysList(layer)
        if polys.OutlineCount() and polys.Collide(seg, need):
            return False
    return True


def _add_track(b, net, layer, p1, p2, width):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(p1)
    t.SetEnd(p2)
    t.SetWidth(FromMM(width))
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)


def _add_via(b, net, pt, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pt)
    v.SetDrill(FromMM(drill))
    v.SetWidth(FromMM(dia))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    b.Add(v)


def lane_route(b, netname, a, b_pt, xa_cands, xb_cands, ym_cands, inner=pcbnew.In2_Cu, width=0.25,
               a_extra=None):
    """Connect B.Cu point `a` to B.Cu point `b_pt` through an inner-layer U path:
    a -(B.Cu)- via(xa, a.y) -(inner)- (xa, ym) - (xb, ym) - (xb, b.y) - via -(B.Cu)- b_pt.
    `a_extra` = optional list of extra B.Cu polylines (mm) that must also be clear/added."""
    net = b.FindNet(netname)
    nc = net.GetNetCode()
    A, Bp = V(*a), V(*b_pt)
    for xa in xa_cands:
        va = V(xa, a[1])
        if not _clear_point(b, nc, va, 0.3) or not _clear_segment(b, nc, pcbnew.B_Cu, A, va, width):
            continue
        for xb in xb_cands:
            vb = V(xb, b_pt[1])
            if not _clear_point(b, nc, vb, 0.3) or not _clear_segment(b, nc, pcbnew.B_Cu, vb, Bp, width):
                continue
            for ym in ym_cands:
                p1, p2 = V(xa, ym), V(xb, ym)
                if (_clear_segment(b, nc, inner, va, p1, width) and _clear_segment(b, nc, inner, p1, p2, width)
                        and _clear_segment(b, nc, inner, p2, vb, width)):
                    ok = True
                    for poly in (a_extra or []):
                        for q1, q2 in zip(poly, poly[1:]):
                            if not _clear_segment(b, nc, pcbnew.B_Cu, V(*q1), V(*q2), width):
                                ok = False
                    if not ok:
                        continue
                    _add_track(b, net, pcbnew.B_Cu, A, va, width)
                    _add_via(b, net, va)
                    _add_track(b, net, inner, va, p1, width)
                    _add_track(b, net, inner, p1, p2, width)
                    _add_track(b, net, inner, p2, vb, width)
                    _add_via(b, net, vb)
                    _add_track(b, net, pcbnew.B_Cu, vb, Bp, width)
                    for poly in (a_extra or []):
                        for q1, q2 in zip(poly, poly[1:]):
                            _add_track(b, net, pcbnew.B_Cu, V(*q1), V(*q2), width)
                    print(f"routed {netname}: xa={xa} ym={ym} xb={xb}")
                    return True
    print(f"NO PATH for {netname}")
    return False


def inner_route(b, netname, a_poly, via_a, via_b, b_poly, ym_cands, inner=pcbnew.In2_Cu, width=0.25):
    """a_poly: B.Cu polyline from a pad to via_a; b_poly: from via_b to a pad. Inner U path at ym."""
    net = b.FindNet(netname)
    nc = net.GetNetCode()
    A = [V(*p) for p in a_poly]
    Bl = [V(*p) for p in b_poly]
    va, vb = V(*via_a), V(*via_b)
    if not (_clear_point(b, nc, va, 0.3) and _clear_point(b, nc, vb, 0.3)):
        print(f"{netname}: via spots blocked"); return False
    if not all(_clear_segment(b, nc, pcbnew.B_Cu, p1, p2, width) for p1, p2 in zip(A, A[1:])):
        print(f"{netname}: A stub blocked"); return False
    if not all(_clear_segment(b, nc, pcbnew.B_Cu, p1, p2, width) for p1, p2 in zip(Bl, Bl[1:])):
        print(f"{netname}: B stub blocked"); return False
    for ym in ym_cands:
        p1, p2 = V(via_a[0], ym), V(via_b[0], ym)
        if (_clear_segment(b, nc, inner, va, p1, width) and _clear_segment(b, nc, inner, p1, p2, width)
                and _clear_segment(b, nc, inner, p2, vb, width)):
            for q1, q2 in zip(A, A[1:]):
                _add_track(b, net, pcbnew.B_Cu, q1, q2, width)
            _add_via(b, net, va)
            _add_track(b, net, inner, va, p1, width)
            _add_track(b, net, inner, p1, p2, width)
            _add_track(b, net, inner, p2, vb, width)
            _add_via(b, net, vb)
            for q1, q2 in zip(Bl, Bl[1:]):
                _add_track(b, net, pcbnew.B_Cu, q1, q2, width)
            print(f"routed {netname} via inner lane ym={ym}")
            return True
    print(f"NO INNER LANE for {netname}")
    return False


def frange(a, b, step):
    out = []
    x = a
    while (x <= b + 1e-9) if step > 0 else (x >= b - 1e-9):
        out.append(round(x, 3))
        x += step
    return out


def direct_route(b, netname, candidates, width=0.25, layer=pcbnew.B_Cu):
    """Add the first candidate polyline (list of (x, y) mm) that clears other-net copper."""
    net = b.FindNet(netname)
    nc = net.GetNetCode()
    for poly in candidates:
        pts = [V(*p) for p in poly]
        if all(_clear_segment(b, nc, layer, p1, p2, width) for p1, p2 in zip(pts, pts[1:])):
            for p1, p2 in zip(pts, pts[1:]):
                _add_track(b, net, layer, p1, p2, width)
            print(f"routed {netname} directly: {poly}")
            return True
    print(f"NO DIRECT PATH for {netname}")
    return False


def pad_xy(b, ref, num):
    for fp in b.GetFootprints():
        if fp.GetReference() == ref:
            p = fp.FindPadByNumber(num).GetPosition()
            return (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))
    raise KeyError(ref)


def manual():
    b = pcbnew.LoadBoard(PCB)
    apply_rules(b)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    # C3 GND pad island -> R1 GND pad, squeezed between C4 and the input stud pad (0.2 mm track)
    g, r = pad_xy(b, "C3", "2"), pad_xy(b, "R1", "2")
    direct_route(b, "GND", [[g, (35.6, g[1]), (35.6, r[1]), r]], width=0.2)
    # IS4: R405 pad 2 -> sideways to a via clear of the inner IS5/IS6 lanes, inner U, via right of
    # the module pin column (past the router's IS5 via), stub into U10 pad 5 slightly above centre
    a, bp = pad_xy(b, "R405", "2"), pad_xy(b, "U10", "5")
    # IS4 now lives on IO2 (module pin 38, left column): move the net on the board pads, then
    # route along the free left-edge strip and an F.Cu lane in the corridor.
    net_is4 = b.FindNet("IS4")
    for fp_ in b.GetFootprints():
        if fp_.GetReference() == "U10":
            fp_.FindPadByNumber("5").SetNet(b.FindNet("unconnected-(U10-IO5-Pad5)") or b.FindNet(""))
            fp_.FindPadByNumber("38").SetNet(net_is4)
    b.BuildConnectivity()
    bp = pad_xy(b, "U10", "38")
    via_a, via_b = (99.5, 45.4), (1.0, bp[1])
    nc4 = net_is4.GetNetCode()
    stubs_ok = (_clear_point(b, nc4, V(*via_a), 0.3) and _clear_point(b, nc4, V(*via_b), 0.3)
                and _clear_segment(b, nc4, pcbnew.B_Cu, V(*a), V(99.5, a[1]), 0.25)
                and _clear_segment(b, nc4, pcbnew.B_Cu, V(99.5, a[1]), V(*via_a), 0.25)
                and _clear_segment(b, nc4, pcbnew.B_Cu, V(*via_b), V(*bp), 0.25))
    print("IS4 stubs/vias clear:", stubs_ok)
    if stubs_ok:
        poly = grid_route(b, "IS4", pcbnew.F_Cu, via_a, via_b, (0.4, 0.6, 101.0, 53.0))
        if poly:
            _add_track(b, net_is4, pcbnew.B_Cu, V(*a), V(99.5, a[1]), 0.25)
            _add_track(b, net_is4, pcbnew.B_Cu, V(99.5, a[1]), V(*via_a), 0.25)
            _add_via(b, net_is4, V(*via_a))
            _add_via(b, net_is4, V(*via_b))
            _add_track(b, net_is4, pcbnew.B_Cu, V(*via_b), V(*bp), 0.25)
    # +3V3 at D401 pad 2: the inner-layer lane lost its via; put one at the pad's B.Cu stub end
    net3 = b.FindNet("+3V3")
    pd = V(*pad_xy(b, "D401", "2"))
    end = None
    for t in b.Tracks():
        if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net3.GetNetCode() and t.GetLayer() == pcbnew.B_Cu:
            for e, o in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                if (e - pd).EuclideanNorm() < FromMM(0.05):
                    end = o
    inner_end = None
    for t in b.Tracks():
        if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net3.GetNetCode() and t.GetLayer() == pcbnew.In2_Cu:
            seg = pcbnew.SEG(t.GetStart(), t.GetEnd())
            if end is not None and seg.Distance(end) < FromMM(0.3):
                inner_end = seg.NearestPoint(end)
    print("+3V3 D401: B.Cu stub end", end and (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y)), "inner end",
          inner_end and (pcbnew.ToMM(inner_end.x), pcbnew.ToMM(inner_end.y)))
    if end is not None and inner_end is not None:
        spot = end if _clear_point(b, net3.GetNetCode(), end, 0.3) else (inner_end if _clear_point(b, net3.GetNetCode(), inner_end, 0.3) else None)
        if spot is not None and _clear_segment(b, net3.GetNetCode(), pcbnew.In2_Cu, inner_end, spot, 0.25) \
                and _clear_segment(b, net3.GetNetCode(), pcbnew.B_Cu, end, spot, 0.25):
            _add_via(b, net3, spot)
            if (spot - inner_end).EuclideanNorm() > 0:
                _add_track(b, net3, pcbnew.In2_Cu, inner_end, spot, 0.25)
            if (spot - end).EuclideanNorm() > 0:
                _add_track(b, net3, pcbnew.B_Cu, end, spot, 0.25)
            print("+3V3 D401 via placed at", pcbnew.ToMM(spot.x), pcbnew.ToMM(spot.y))
        else:
            print("+3V3 D401: no clear via spot")
    # USB D-: the router parked the D+ via in the D- escape lane. Move the D+ via 1 mm and
    # give D- its own via + inner path to the already-routed D- fragment.
    dp, dm = b.FindNet("USB_D+"), b.FindNet("USB_D-")
    for t in list(b.Tracks()):
        if t.GetNetCode() == dp.GetNetCode():
            if t.GetClass() == "PCB_VIA" and (t.GetPosition() - V(11.86, 51.49)).EuclideanNorm() < FromMM(0.05):
                b.Remove(t)
            elif t.GetClass() == "PCB_TRACK" and (
                    (t.GetStart() - V(11.86, 51.49)).EuclideanNorm() < FromMM(0.05) or
                    (t.GetEnd() - V(11.86, 51.49)).EuclideanNorm() < FromMM(0.05)):
                b.Remove(t)
    b.BuildConnectivity()
    ncp, ncm = dp.GetNetCode(), dm.GetNetCode()
    plan = [
        (ncp, pcbnew.B_Cu, (11.12, 50.75), (11.9, 50.5), 0.25),
        (ncp, pcbnew.In2_Cu, (11.9, 50.5), (16.91, 46.45), 0.25),
        (ncm, pcbnew.B_Cu, (9.68, 51.75), (11.2, 51.75), 0.25),
        (ncm, pcbnew.In2_Cu, (11.2, 51.75), (11.2, 46.4), 0.25),
        (ncm, pcbnew.In2_Cu, (11.2, 46.4), (12.1, 45.72), 0.25),
    ]
    ok = all(_clear_segment(b, nc_, lay, V(*p1), V(*p2), w) for nc_, lay, p1, p2, w in plan)
    ok = ok and _clear_point(b, ncp, V(11.9, 50.5), 0.3) and _clear_point(b, ncm, V(11.2, 51.75), 0.3)
    if ok:
        for nc_, lay, p1, p2, w in plan:
            _add_track(b, dp if nc_ == ncp else dm, lay, V(*p1), V(*p2), w)
        _add_via(b, dp, V(11.9, 50.5))
        _add_via(b, dm, V(11.2, 51.75))
        print("USB D+/D- via relocation applied")
    else:
        print("USB D+/D- plan blocked:", [(_clear_segment(b, nc_, lay, V(*p1), V(*p2), w), p1, p2) for nc_, lay, p1, p2, w in plan],
              _clear_point(b, ncp, V(11.9, 50.5), 0.3), _clear_point(b, ncm, V(11.2, 51.75), 0.3))
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
    print("saved", PCB)




def _try_polyline(b, netname, layer, pts, width=0.25):
    net = b.FindNet(netname)
    nc = net.GetNetCode()
    P = [V(*p) for p in pts]
    for p1, p2 in zip(P, P[1:]):
        if not _clear_segment(b, nc, layer, p1, p2, width):
            print(f"polyline for {netname} blocked at {p1} -> {p2}")
            return False
    for p1, p2 in zip(P, P[1:]):
        _add_track(b, net, layer, p1, p2, width)
    print(f"added polyline for {netname}")
    return True


def manual2():
    b = pcbnew.LoadBoard(PCB)
    apply_rules(b)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    # +3V3: R5 pad 1 end (24.0, 11.88) around C9's GND pad to C9 pad 1 (24.0, 8.55)
    if not _try_polyline(b, "+3V3", pcbnew.B_Cu, [(24.0, 11.88), (23.0, 11.88), (23.0, 8.55), (24.0, 8.55)], 0.3):
        lane_route(b, "+3V3", (24.0, 11.88), (24.0, 8.55), frange(22.2, 23.4, 0.1), frange(22.2, 23.4, 0.1),
                   frange(8.0, 12.5, 0.1), width=0.3)
    # RT: U9 pad 4 -> R1 pad 1 via the inner layer
    lane_route(b, "RT", (32.5, 10.9), (34.8, 14.88), frange(31.0, 33.6, 0.1), frange(35.3, 35.7, 0.05),
               frange(6.0, 21.0, 0.1))
    # IS3: R305 pad 2 -> U10 pad 4 (right column)
    lane_route(b, "IS3", (82.9, 46.83), (20.75, 7.15), frange(80.8, 86.0, 0.2), frange(22.0, 23.6, 0.1),
               frange(41.0, 50.6, 0.1))
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
    persist_project_rules(PCB)
    print("saved", PCB)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "manual2":
    manual2()


# ----------------------------------------------------------------------------- grid router
def grid_route(b, netname, layer, start, goal, region, step=0.2, width=0.25, turn_cost=3):
    """Single-layer Manhattan router on a grid with clearance-expanded obstacles.

    start/goal: (x, y) mm (must be free cells). region: (x0, y0, x1, y1) mm. Returns polyline or None.
    """
    import heapq
    net = b.FindNet(netname)
    nc = net.GetNetCode()
    x0, y0, x1, y1 = region
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    blocked = bytearray(nx * ny)
    half = width / 2 + CLR

    def cell(x, y):
        return int(round((x - x0) / step)), int(round((y - y0) / step))

    def mark_circle(cx, cy, r):
        ci, cj = (cx - x0) / step, (cy - y0) / step
        rr = r / step
        i0, i1 = max(0, int(ci - rr) - 1), min(nx - 1, int(ci + rr) + 1)
        j0, j1 = max(0, int(cj - rr) - 1), min(ny - 1, int(cj + rr) + 1)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if (i - ci) ** 2 + (j - cj) ** 2 <= rr * rr:
                    blocked[j * nx + i] = 1

    def mark_segment(ax, ay, bx, by, r):
        L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        n = max(1, int(L / (step * 0.5)))
        for k in range(n + 1):
            t = k / n
            mark_circle(ax + (bx - ax) * t, ay + (by - ay) * t, r)

    mm = pcbnew.ToMM
    for t in b.Tracks():
        if t.GetNetCode() == nc:
            continue
        if t.GetClass() == "PCB_VIA":
            mark_circle(mm(t.GetPosition().x), mm(t.GetPosition().y), 0.35 + half)
        elif t.GetLayer() == layer:
            mark_segment(mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y),
                         mm(t.GetWidth()) / 2 + half)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == nc and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                continue
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                mark_circle(mm(p.GetPosition().x), mm(p.GetPosition().y), mm(p.GetDrillSize().x) / 2 + half)
            elif p.IsOnLayer(layer) or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                # rectangular pads: use the half-diagonal so corners are covered
                mark_circle(mm(p.GetPosition().x), mm(p.GetPosition().y),
                            (mm(p.GetSize().x) ** 2 + mm(p.GetSize().y) ** 2) ** 0.5 / 2 + half)
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() == nc or z.GetNetname() == "GND" or not z.IsOnLayer(layer):
            continue
        polys = z.GetFilledPolysList(layer)
        if not polys.OutlineCount():
            continue
        bb = polys.BBox()
        i0, j0 = cell(max(x0, mm(bb.GetLeft()) - half), max(y0, mm(bb.GetTop()) - half))
        i1, j1 = cell(min(x1, mm(bb.GetRight()) + half), min(y1, mm(bb.GetBottom()) + half))
        clr = FromMM(half)
        for i in range(max(0, i0), min(nx, i1 + 1)):
            for j in range(max(0, j0), min(ny, j1 + 1)):
                if polys.Collide(V(x0 + i * step, y0 + j * step), clr):
                    blocked[j * nx + i] = 1
    bb = b.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = mm(bb.GetLeft()) + 0.3 + half, mm(bb.GetTop()) + 0.3 + half, mm(bb.GetRight()) - 0.3 - half, mm(bb.GetBottom()) - 0.3 - half
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + i * step, y0 + j * step
            if x < ex0 or x > ex1 or y < ey0 or y > ey1:
                blocked[j * nx + i] = 1

    si, sj = cell(*start)
    gi, gj = cell(*goal)
    if blocked[sj * nx + si] or blocked[gj * nx + gi]:
        print(f"grid_route {netname}: start/goal blocked ({not blocked[sj * nx + si]}, {not blocked[gj * nx + gi]})")
        return None
    # Dijkstra with turn penalty; state = (i, j, dir)
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    INF = 1 << 30
    dist = {}
    prev = {}
    pq = []
    for d in range(4):
        dist[(si, sj, d)] = 0
        heapq.heappush(pq, (0, si, sj, d))
    found = None
    while pq:
        c, i, j, d = heapq.heappop(pq)
        if c > dist.get((i, j, d), INF):
            continue
        if (i, j) == (gi, gj):
            found = (i, j, d)
            break
        for nd, (dx, dy) in enumerate(dirs):
            ni, nj = i + dx, j + dy
            if ni < 0 or nj < 0 or ni >= nx or nj >= ny or blocked[nj * nx + ni]:
                continue
            ncst = c + 1 + (turn_cost if nd != d else 0)
            if ncst < dist.get((ni, nj, nd), INF):
                dist[(ni, nj, nd)] = ncst
                prev[(ni, nj, nd)] = (i, j, d)
                heapq.heappush(pq, (ncst, ni, nj, nd))
    if found is None:
        print(f"grid_route {netname}: no path")
        return None
    cells = []
    s = found
    while s in prev:
        cells.append((s[0], s[1]))
        s = prev[s]
    cells.append((si, sj))
    cells.reverse()
    pts = [cells[0]]
    for k in range(1, len(cells) - 1):
        (ax, ay), (bx, by), (cx, cy) = cells[k - 1], cells[k], cells[k + 1]
        if (bx - ax, by - ay) != (cx - bx, cy - by):
            pts.append(cells[k])
    pts.append(cells[-1])
    poly = [(round(x0 + i * step, 3), round(y0 + j * step, 3)) for i, j in pts]
    for p1, p2 in zip(poly, poly[1:]):
        _add_track(b, net, layer, V(*p1), V(*p2), width)
    print(f"grid_route {netname}: {len(poly) - 1} segments")
    return poly


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "manual":
    manual()
