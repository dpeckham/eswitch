"""Revision B heavy-copper stackup and USB reference-plane constraints.

JLCPCB's public calculator, observed 2026-09-16: JLC041622-3313,
1.6 mm nominal, 2 oz outer/inner, L4 referenced to L3, 90 ohms differential.
At 0.214 mm spacing it returned 0.2334 mm width (0.5% solver tolerance).
The routed 0.450 mm pitch uses 0.235 mm width / 0.215 mm straight-run gap.
"""
import math
import pcbnew


STACKUP = '''
\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.0152) (epsilon_r 3.8) (loss_tangent 0.02))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.07))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.1835) (material "3313 RC57% x2") (epsilon_r 4.1) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.061))
\t\t\t(layer "dielectric 2" (type "core") (thickness 0.96) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.061))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.1835) (material "3313 RC57% x2") (epsilon_r 4.1) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.07))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.0152) (epsilon_r 3.8) (loss_tangent 0.02))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints yes)
\t\t)
'''


def ensure_stackup(serialized):
    """The SWIG stackup descriptor is opaque; insert into new generated files."""
    if "(stackup" not in serialized:
        serialized = serialized.replace("(setup\n", "(setup\n" + STACKUP, 1)
    return serialized


def configure_usb(board):
    """Non-coplanar pair on B.Cu; preserve an unbroken In2 ground reference."""
    for z in list(board.Zones()):
        if z.GetZoneName().startswith("usb_reference_"):
            board.Remove(z)
    count=0
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname().removeprefix("/") not in (
                "USB_D+", "USB_D-", "USB_MCU_D+", "USB_MCU_D-"):
            continue
        t.SetWidth(pcbnew.FromMM(.235))
        x1,y1=pcbnew.ToMM(t.GetStart().x),pcbnew.ToMM(t.GetStart().y)
        x2,y2=pcbnew.ToMM(t.GetEnd().x),pcbnew.ToMM(t.GetEnd().y)
        if max(x1,x2)<14.2:
            continue  # short connector/ESD pin breakout, not the long pair
        length=math.hypot(x2-x1,y2-y1)
        if not length:
            continue
        dx,dy=(x2-x1)/length,(y2-y1)/length
        m=.9
        pts=[(x1-dx*m-dy*m,y1-dy*m+dx*m),(x2+dx*m-dy*m,y2+dy*m+dx*m),
             (x2+dx*m+dy*m,y2+dy*m-dx*m),(x1-dx*m+dy*m,y1-dy*m-dx*m)]
        for layer in (pcbnew.B_Cu, pcbnew.In2_Cu):
            z=pcbnew.ZONE(board)
            z.SetIsRuleArea(True)
            z.SetLayer(layer)
            z.SetDoNotAllowTracks(layer==pcbnew.In2_Cu)
            z.SetDoNotAllowVias(False)
            z.SetDoNotAllowPads(False)
            z.SetDoNotAllowFootprints(False)
            z.SetDoNotAllowZoneFills(layer==pcbnew.B_Cu)
            z.SetZoneName(f"usb_reference_{count}")
            z.AddPolygon(pcbnew.VECTOR_VECTOR2I([pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)) for x,y in pts]))
            board.Add(z)
            count+=1


if __name__ == "__main__":
    from pathlib import Path
    from pcb_io import save_board
    from gen_pcb import apply_rules
    path=Path(__file__).resolve().parent.parent/"eswitch.kicad_pcb"
    b=pcbnew.LoadBoard(str(path))
    apply_rules(b)
    configure_usb(b)
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    save_board(path,b)
