"""Local escapes for three signal gaps inherited from the 221 mm checkpoint.

Called once by the serialized migration, after the 32 mm insertion. These edits
are specific to that source snapshot; assertions prevent accidental reapplication.
"""
import pcbnew
from gen_pcb import V
from pcb_nets import find_net, short_name


def xy(point):
    return pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)


def repair_fanout(board):
    def track(net, points):
        for start, end in zip(points, points[1:]):
            item = pcbnew.PCB_TRACK(board)
            item.SetStart(V(*start))
            item.SetEnd(V(*end))
            item.SetWidth(pcbnew.FromMM(.2))
            item.SetLayer(pcbnew.B_Cu)
            item.SetNet(find_net(board, net))
            board.Add(item)

    def via(net, x, y, diameter=.6):
        assert not any(t.GetClass() == "PCB_VIA" and t.GetPosition() == V(x, y)
                       for t in board.GetTracks()), "Fanout already applied or source differs"
        item = pcbnew.PCB_VIA(board)
        item.SetPosition(V(x, y))
        item.SetWidth(pcbnew.FromMM(diameter))
        item.SetDrill(pcbnew.FromMM(.3))
        item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        item.SetNet(find_net(board, net))
        board.Add(item)

    u3 = board.FindFootprintByReference("U3")
    assert u3.GetPosition() == V(161.1, 35), "Requires translated revision-B layout"
    track("ISP3", [(158.255, 35), (159.2, 35)])
    via("ISP3", 159.2, 35, .5)

    # Give INR2 room to escape between the adjacent input and diagnosis pins.
    changed = 0
    for item in board.GetTracks():
        if item.GetClass() != "PCB_TRACK" or short_name(item) != "DENR2":
            continue
        # Copy endpoint coordinates before modifying a live C++ vector.
        start, end = xy(item.GetStart()), xy(item.GetEnd())
        for point, setter in ((start, item.SetStart), (end, item.SetEnd)):
            if all(abs(a-b) < .00001 for a, b in zip(point, (141.2525, 36.4258))):
                setter(V(141.2525, 35.65))
                changed += 1
    assert changed == 2, ("Unexpected DENR2 source geometry", changed)
    track("INR2", [(143.01, 36.3), (142, 36.3)])
    via("INR2", 142, 36.3)

    # Remove the GND daisy-chain enclosing R301. Its passive returns use the
    # adjacent pour and separately checked stitches to the continuous In1 plane.
    detached = []
    for item in list(board.GetTracks()):
        if item.GetClass() != "PCB_TRACK" or short_name(item) != "GND" or item.GetLayer() != pcbnew.B_Cu:
            continue
        start, end = xy(item.GetStart()), xy(item.GetEnd())
        if all(154.8 <= x <= 161.4 and 40.5 <= y <= 43.7 for x, y in (start, end)) and max(start[1], end[1]) > 41:
            detached.append(item)
    assert len(detached) == 7, ("Unexpected channel-3 ground routing", len(detached))
    for item in detached:
        board.Remove(item)
    track("IN3", [(157.3, 42.175), (156.3, 42.175), (156.3, 42.125)])
    via("IN3", 156.3, 42.125)
    return detached  # Hold removed SWIG objects through the caller's save.
