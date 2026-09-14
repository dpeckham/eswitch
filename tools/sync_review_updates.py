#!/usr/bin/env python3
"""Apply review corrections without discarding the existing routed board.

Run after `just libs sch netlist` with KiCad's Python. This migrates the original
16-pole output footprint into eight two-pole blocks at exactly the same holes,
updates input terminal hole patterns and assembly fields, and applies the
reviewed edge/drill constraints. Input terminal changes require local rerouting.
It does not reroute the buck, USB, antenna area, or input protection.
"""
import os

import pcbnew

import design
from gen_pcb import CX, Y_TERM, V, apply_rules, persist_project_rules, fuse_silk_labels
from sexp import parse_one, find, find_all

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "eswitch.kicad_pcb")


def main():
    parts = {p.ref: p for p in design.build() if p.footprint}
    b = pcbnew.LoadBoard(PCB)
    old = b.FindFootprintByReference("J1")
    if str(old.GetFPID().GetLibItemName()) == "TerminalBlock_1x16_P7.62mm_Wuerth_3114":
        expected = {}
        for p in old.Pads():
            expected[int(p.GetNumber())] = (p.GetPosition().x, p.GetPosition().y, p.GetNetname())
        replacements = []
        for i, ref in enumerate(design.OUTPUT_REFS):
            if ref != "J1" and b.FindFootprintByReference(ref):
                raise RuntimeError(f"Refusing to replace existing {ref}")
            fp = pcbnew.FootprintLoad(os.path.join(ROOT, "lib", "eswitch.pretty"),
                                     design.OUTPUT_FOOTPRINT.split(":")[1])
            fp.SetReference(ref)
            fp.SetPosition(V(CX[i] - 3.81, Y_TERM))
            fp.Reference().SetVisible(False)
            for pad in fp.Pads():
                n = int(pad.GetNumber())
                net = parts[ref].pins[str(n)]
                x, y, old_net = expected[2 * i + n]
                assert (pad.GetPosition() - pcbnew.VECTOR2I(x, y)).EuclideanNorm() <= 1
                assert net == old_net, (ref, n, net, old_net)
                pad.SetNet(b.FindNet(net))
            replacements.append(fp)
        b.Remove(old)
        for fp in replacements:
            b.Add(fp)
        # Move channel/polarity markings out from underneath the deeper bodies.
        for item in b.GetDrawings():
            if item.GetClass() != "PCB_TEXT" or item.GetLayer() != pcbnew.F_SilkS:
                continue
            p = item.GetPosition()
            y = pcbnew.ToMM(p.y)
            if item.GetText().startswith("CH") and abs(y - 47.0) < 0.01:
                item.SetPosition(pcbnew.VECTOR2I(p.x, pcbnew.FromMM(43.8)))
            elif item.GetText() in ("+", "-") and abs(y - 49.3) < 0.01:
                item.SetPosition(pcbnew.VECTOR2I(p.x, pcbnew.FromMM(46.0)))
    elif str(old.GetFPID().GetLibItemName()) != design.OUTPUT_FOOTPRINT.split(":")[1]:
        raise RuntimeError("Unexpected J1 footprint; inspect before migration")

    inputs = [(ref, b.FindFootprintByReference(ref)) for ref in ("J2", "J3")]
    inputs = [(ref, fp, str(fp.GetFPID().GetLibItemName()), fp.GetPosition())
              for ref, fp in inputs]
    for ref, old, name, position in inputs:
        if name == design.INPUT_FOOTPRINT.split(":")[1]:
            continue
        if name != "ScrewTerminal_Keystone_8196_10-32":
            raise RuntimeError(f"Unexpected {ref} footprint; inspect before migration")
        fp = pcbnew.FootprintLoad(os.path.join(ROOT, "lib", "eswitch.pretty"),
                                 design.INPUT_FOOTPRINT.split(":")[1])
        fp.SetReference(ref)
        fp.SetPosition(position)
        fp.Reference().SetVisible(False)
        for pad in fp.Pads():
            pad.SetNet(b.FindNet(parts[ref].pins["1"]))
            # The common 40 A path must not depend on narrow thermal spokes.
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        b.Remove(old)
        b.Add(fp)

    netlist = parse_one(open(os.path.join(ROOT, "out", "eswitch.net")).read())
    comps = {find(c, "ref")[1]: c for c in find_all(find(netlist, "components"), "comp")}
    for fp in b.GetFootprints():
        part = parts[fp.GetReference()]
        fp.SetFPID(pcbnew.LIB_ID(*part.footprint.split(":", 1)))
        fp.SetValue(part.value)
        for name, value in part.fields.items():
            fp.SetField(name, value)
            field = fp.GetField(name)
            field.SetVisible(False)
            field.SetLayer(pcbnew.B_Fab if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_Fab)
            field.SetMirrored(fp.GetLayer() == pcbnew.B_Cu)
        if part.ref in design.OUTPUT_REFS:
            for pad in fp.Pads():
                pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        path = pcbnew.KIID_PATH()
        path.push_back(pcbnew.KIID(find(comps[part.ref], "tstamps")[1]))
        fp.SetPath(path)
        if part.ref == "U10":
            for pad in fp.Pads():
                if 0 < pad.GetDrillSize().x < pcbnew.FromMM(0.254):
                    pad.SetDrillSize(V(0.254, 0.254))
    # Separate fuse limits from channel identity; do not advertise continuous
    # current qualification in the channel labels. Upstream fuse is separate.
    for item in b.GetDrawings():
        if item.GetClass() != "PCB_TEXT":
            continue
        for n, (rating, _, _) in design.CHANNELS.items():
            if item.GetText() == f"CH{n} {rating}A":
                item.SetText(f"CH{n}")
            if (item.GetText() == f"MAX FUSE {rating}A"
                    and abs(pcbnew.ToMM(item.GetPosition().x) - CX[n - 1] - 5.2) < 0.01):
                item.SetText(f"CH{n} MAX FUSE {rating}A")
    labels = {i.GetText(): i for i in b.GetDrawings() if i.GetClass() == "PCB_TEXT"}
    for content, x, y, layer, size, rot in fuse_silk_labels():
        t = labels.get(content)
        if t is None:
            t = pcbnew.PCB_TEXT(b)
            b.Add(t)
        t.SetText(content)
        t.SetPosition(V(x, y))
        t.SetLayer(layer)
        t.SetTextSize(V(size, size))
        t.SetTextThickness(pcbnew.FromMM(0.15))
        t.SetTextAngleDegrees(rot)
        t.SetMirrored(layer == pcbnew.B_SilkS)
    apply_rules(b)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
    persist_project_rules(PCB)
    print("Updated terminals, assembly fields, fuse labels, and fabrication constraints")


if __name__ == "__main__":
    main()
