#!/usr/bin/env python3
"""Generate the project-local KiCad libraries (lib/eswitch.pretty, lib/eswitch.kicad_sym)."""
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexp import parse_one, dump, find, find_all, Sym  # noqa: E402
import kicad_env  # noqa: E402

PRETTY = os.path.join(ROOT, "lib", "eswitch.pretty")
SYMLIB = os.path.join(ROOT, "lib", "eswitch.kicad_sym")

# --------------------------------------------------------------------------- footprints
FP_HEADER = """(footprint "{name}"
\t(version 20260206)
\t(generator "eswitch_gen_libs")
\t(generator_version "10.0")
\t(layer "F.Cu")
\t(descr "{descr}")
\t(tags "{tags}")
\t(property "Reference" "REF**"
\t\t(at {refx} {refy} 0)
\t\t(layer "F.SilkS")
\t\t(effects (font (size 1 1) (thickness 0.15)))
\t)
\t(property "Value" "{name}"
\t\t(at {valx} {valy} 0)
\t\t(layer "F.Fab")
\t\t(effects (font (size 1 1) (thickness 0.15)))
\t)
\t(property "Datasheet" "{datasheet}"
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(effects (font (size 1.27 1.27) (thickness 0.15)))
\t)
\t(property "Description" "{descr}"
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(effects (font (size 1.27 1.27) (thickness 0.15)))
\t)
\t(attr through_hole)
\t(duplicate_pad_numbers_are_jumpers no)
"""


def line(x1, y1, x2, y2, layer, w=0.12, style="solid"):
    return (f"\t(fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) "
            f"(stroke (width {w}) (type {style})) (layer \"{layer}\"))\n")


def rect(x1, y1, x2, y2, layer, w=0.12, style="solid"):
    return (f"\t(fp_rect (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) "
            f"(stroke (width {w}) (type {style})) (fill no) (layer \"{layer}\"))\n")


def circle(cx, cy, r, layer, w=0.12):
    return (f"\t(fp_circle (center {cx:.3f} {cy:.3f}) (end {cx + r:.3f} {cy:.3f}) "
            f"(stroke (width {w}) (type solid)) (fill no) (layer \"{layer}\"))\n")


def text(s, x, y, layer, size=0.8, rot=0, thick=0.12):
    return (f"\t(fp_text user \"{s}\" (at {x:.3f} {y:.3f} {rot}) (layer \"{layer}\") "
            f"(effects (font (size {size} {size}) (thickness {thick}))))\n")


def tht(num, x, y, size, drill, shape="circle"):
    return (f"\t(pad \"{num}\" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {size} {size}) "
            f"(drill {drill}) (layers \"*.Cu\" \"*.Mask\") (remove_unused_layers no))\n")


def npth(x, y, d):
    return (f"\t(pad \"\" np_thru_hole circle (at {x:.3f} {y:.3f}) (size {d} {d}) "
            f"(drill {d}) (layers \"*.Cu\" \"*.Mask\"))\n")


def write_fp(name, body, descr, tags, datasheet="", ref=(0, -1.5), val=(0, 1.5)):
    s = FP_HEADER.format(name=name, descr=descr, tags=tags, datasheet=datasheet,
                         refx=ref[0], refy=ref[1], valx=val[0], valy=val[1])
    s += body + "\t(embedded_fonts no)\n"
    s += ('\t(model "${KIPRJMOD}/lib/eswitch.3dshapes/%s.wrl" (offset (xyz 0 0 0)) '
          '(scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n)\n' % name)
    os.makedirs(PRETTY, exist_ok=True)
    with open(os.path.join(PRETTY, name + ".kicad_mod"), "w") as f:
        f.write(s)
    print("wrote", name)


def fp_fuseholder():
    """Three Keystone 3557 clips in a line at ATO blade pitch (9.27 mm).

    Origin = blade position of the centre (COM) clip. Blade 1 (SW) at y=-9.27, blade 3
    (BYP) at y=+9.27. Each clip has two 1.6 mm pins on 3.4 mm centres, located 2.1 mm
    outboard of its blade (Keystone drawing: L = 13.46 mm between clip pin pairs for a
    standard fuse whose blades are 9.27 mm apart).
    """
    P = 9.27
    OFF = 2.1
    b = ""
    clips = [("1", -P, -OFF), ("2", 0.0, +OFF), ("3", P, +OFF)]
    for num, blade, off in clips:
        py = blade + off
        for px in (-1.7, 1.7):
            b += tht(num, px, py, 2.8, 1.7)
        # clip body 3.81 x 4.70; pin sits ~0.8 mm from the outboard edge
        if off > 0:
            y1, y2 = blade - 1.8, blade + 2.9
        else:
            y1, y2 = blade - 2.9, blade + 1.8
        b += rect(-1.905, y1, 1.905, y2, "F.Fab", 0.1)
    # fuse body outlines (19.1 x 5.1 mm): AUTO position (blades 1-2), BYPASS (blades 2-3)
    b += rect(-2.55, -P / 2 - 9.55, 2.55, -P / 2 + 9.55, "F.Fab", 0.1)
    b += rect(-2.55, P / 2 - 9.55, 2.55, P / 2 + 9.55, "F.Fab", 0.1, "dash")
    b += rect(-3.5, -P / 2 - 9.75, 3.5, -P / 2 + 9.75, "F.SilkS", 0.12, "dash")
    b += rect(-3.5, P / 2 - 9.75, 3.5, P / 2 + 9.75, "F.SilkS", 0.12, "dot")
    b += text("AUTO", -4.6, -P / 2, "F.SilkS", 0.9, 90)
    b += text("BYPASS", 4.6, P / 2, "F.SilkS", 0.9, 90)
    b += text("SW", -4.3, -P - 2.1, "F.Fab", 0.6, 90)
    b += text("COM", -4.3, 0, "F.Fab", 0.6, 90)
    b += text("LOAD", -4.3, P + 2.1, "F.Fab", 0.6, 90)
    b += text("${REFERENCE}", 0, 0, "F.Fab", 0.6, 90)
    b += rect(-3.05, -P / 2 - 9.55 - 0.25, 3.05, P / 2 + 9.55 + 0.25, "F.CrtYd", 0.05)
    write_fp("Fuseholder_ATO_3pos_Keystone_3557", b,
             "3-position ATO/ATC blade fuse holder made of 3x Keystone 3557 clips at 9.27mm blade pitch; "
             "fuse straddles clips 1-2 (AUTO) or 2-3 (BYPASS)",
             "fuse holder ATO ATC blade Keystone 3557", "https://www.keyelco.com/product.cfm/product_id/1131",
             ref=(0, -16.5), val=(0, 16.5))


def fp_screw_terminal_8196():
    """Keystone 8196 heavy-duty PC screw terminal, 10-32 screw, 30 A, 6 legs."""
    b = ""
    for x in (-5.2, 0.0, 5.2):
        for y in (-5.4, 5.4):
            b += tht("1", x, y, 3.8, 2.6)
    b += rect(-6.0, -6.0, 6.0, 6.0, "F.Fab", 0.1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b += line(sx * 7.6, sy * 7.6, sx * 7.6, sy * 5.6, "F.SilkS", 0.12)
            b += line(sx * 7.6, sy * 7.6, sx * 5.6, sy * 7.6, "F.SilkS", 0.12)
    b += circle(0, 0, 2.4, "F.Fab", 0.1)
    b += text("10-32", 0, -3.6, "F.Fab", 0.7)
    b += text("${REFERENCE}", 0, 3.6, "F.Fab", 0.7)
    b += rect(-7.7, -7.7, 7.7, 7.7, "F.CrtYd", 0.05)
    write_fp("ScrewTerminal_Keystone_8196_10-32", b,
             "Keystone 8196 heavy duty PC screw terminal, #10-32 x 3/8 screw, 30 A, six 1.52 mm legs in 2.6 mm holes on 5.2 x 10.8 mm pattern",
             "screw terminal Keystone 8196 10-32 ring lug",
             "https://www.keyelco.com/product.cfm/product_id/1289", ref=(0, -8.6), val=(0, 8.6))


def fp_terminal_block_16():
    """16-position 7.62 mm pitch PCB screw terminal block, side wire entry toward +Y.

    Matches Wuerth WR-TBL 3114 (691311400116): 1.0 mm square pins in 1.6 mm holes, body
    3.8 mm behind and 4.7 mm in front of the pin row, 12 mm tall, 20 A.
    """
    N = 16
    P = 7.62
    b = ""
    for i in range(N):
        b += tht(str(i + 1), i * P, 0.0, 2.6, 1.6, "rect" if i == 0 else "circle")
    x1, x2 = -3.8, (N - 1) * P + 3.8
    b += rect(x1, -3.8, x2, 4.7, "F.Fab", 0.1)
    b += rect(x1 - 0.12, -3.92, x2 + 0.12, 4.82, "F.SilkS", 0.12)
    for i in range(N):
        b += line(i * P - 3.0, 4.7, i * P - 3.0, 1.0, "F.Fab", 0.1)
        b += line(i * P + 3.0, 4.7, i * P + 3.0, 1.0, "F.Fab", 0.1)
        b += circle(i * P, -1.0, 1.4, "F.Fab", 0.1)
    b += line(x1 - 0.12, -3.92, x1 - 0.12, -5.0, "F.SilkS", 0.12)  # pin-1 marker
    b += line(x1 - 0.12, -5.0, 1.0, -5.0, "F.SilkS", 0.12)
    b += text("${REFERENCE}", (N - 1) * P / 2, -2.2, "F.Fab", 0.8)
    b += rect(x1 - 0.25, -4.05, x2 + 0.25, 4.95, "F.CrtYd", 0.05)
    write_fp("TerminalBlock_1x16_P7.62mm_Wuerth_3114", b,
             "16-position 7.62 mm PCB screw terminal block, side entry, Wuerth WR-TBL 3114 691311400116 (20 A)",
             "terminal block 7.62mm 16 Wuerth 3114 691311400116",
             "https://www.we-online.com/components/products/datasheet/691311400116.pdf",
             ref=(57.15, -6.0), val=(57.15, 6.2))


# --------------------------------------------------------------------------- symbols
SYM_PROP = """\t\t(property "{key}" "{val}"
\t\t\t(at {x} {y} 0)
{hide}\t\t\t(effects (font (size 1.27 1.27)){just})
\t\t)
"""


def prop(key, val, x, y, hide=False, just=""):
    return SYM_PROP.format(key=key, val=val, x=x, y=y, hide="\t\t\t(hide yes)\n" if hide else "",
                           just=f" (justify {just})" if just else "")


def pin(ptype, x, y, ang, length, name, num, hide=False):
    return (f"\t\t\t(pin {ptype} line (at {x} {y} {ang}) (length {length})"
            f"{' (hide yes)' if hide else ''} (name \"{name}\") (number \"{num}\"))\n")


def sym_fuseholder():
    s = '\t(symbol "FuseHolder_ATO_3pos"\n\t\t(exclude_from_sim yes)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
    s += prop("Reference", "F", -7.62, 8.89)
    s += prop("Value", "FuseHolder_ATO_3pos", 0, 8.89)
    s += prop("Footprint", "eswitch:Fuseholder_ATO_3pos_Keystone_3557", 0, -10.16, True)
    s += prop("Datasheet", "https://www.keyelco.com/product.cfm/product_id/1131", 0, -12.7, True)
    s += prop("Description", "3-position ATO blade fuse holder (3x Keystone 3557 clips): fuse in AUTO "
              "position bridges COM-SW, in BYPASS position bridges COM-LOAD", 0, 0, True)
    s += prop("ki_keywords", "fuse holder ATO bypass", 0, 0, True)
    s += '\t\t(symbol "FuseHolder_ATO_3pos_0_1"\n'
    s += ('\t\t\t(rectangle (start -6.35 6.35) (end 6.35 -6.35) (stroke (width 0.254) (type default)) '
          '(fill (type background)))\n')
    # fuse element drawn between COM and SW (AUTO position)
    s += ('\t\t\t(rectangle (start -4.445 3.81) (end -0.635 1.27) (stroke (width 0.254) (type default)) '
          '(fill (type none)))\n')
    s += ('\t\t\t(polyline (pts (xy -6.35 2.54) (xy -4.445 2.54) (xy -0.635 2.54) (xy 6.35 2.54)) '
          '(stroke (width 0.254) (type default)) (fill (type none)))\n')
    s += ('\t\t\t(polyline (pts (xy -6.35 2.54) (xy -6.35 -2.54)) '
          '(stroke (width 0.254) (type default)) (fill (type none)))\n')
    # dashed fuse element between COM and LOAD (BYPASS position)
    s += ('\t\t\t(rectangle (start -4.445 -1.27) (end -0.635 -3.81) (stroke (width 0.254) (type dash)) '
          '(fill (type none)))\n')
    s += ('\t\t\t(polyline (pts (xy -6.35 -2.54) (xy -4.445 -2.54)) '
          '(stroke (width 0.254) (type dash)) (fill (type none)))\n')
    s += ('\t\t\t(polyline (pts (xy -0.635 -2.54) (xy 6.35 -2.54)) '
          '(stroke (width 0.254) (type dash)) (fill (type none)))\n')
    s += ('\t\t\t(text "AUTO" (at -2.54 5.08 0) (effects (font (size 0.9 0.9))))\n')
    s += ('\t\t\t(text "BYPASS" (at -2.54 -5.08 0) (effects (font (size 0.9 0.9))))\n')
    s += "\t\t)\n"
    s += '\t\t(symbol "FuseHolder_ATO_3pos_1_1"\n'
    s += pin("passive", -8.89, 0, 0, 2.54, "COM", "2")
    s += pin("power_out", 8.89, 2.54, 180, 2.54, "SW", "1")
    s += pin("passive", 8.89, -2.54, 180, 2.54, "LOAD", "3")
    s += "\t\t)\n\t\t(embedded_fonts no)\n\t)\n"
    return s


PROFETS = {
    "BTS7002-1EPP": ("2 mOhm, 21 A nominal", "infineon-bts7002-1epp-datasheet-en.pdf"),
    "BTS7004-1EPP": ("4 mOhm, 15 A nominal", "infineon-bts7004-1epp-datasheet-en.pdf"),
    "BTS7008-1EPP": ("8 mOhm, 11 A nominal", "infineon-bts7008-1epp-datasheet-en.pdf"),
}


def sym_bts7008(new="BTS7008-1EPP"):
    src = kicad_env.symbol_file("Power_Management", "BTS7004-1EPP")
    lib = parse_one(open(src).read())
    sym = find(lib, "symbol")
    old = "BTS7004-1EPP"
    spec, ds = PROFETS[new]

    def rename(node):
        if isinstance(node, list):
            if node and node[0] == "symbol" and isinstance(node[1], str):
                node[1] = node[1].replace(old, new)
            for c in node:
                rename(c)
    rename(sym)
    # GND pin goes through the 47 R ReverseON resistor, so treat it as passive for ERC
    for sub in find_all(sym, "symbol"):
        for pn in find_all(sub, "pin"):
            if find(pn, "number")[1] == "1":
                pn[1] = Sym("passive")
    for p in find_all(sym, "property"):
        if p[1] == "Value":
            p[2] = new
        elif p[1] == "Datasheet":
            p[2] = "https://www.infineon.com/assets/row/public/documents/10/49/" + ds
        elif p[1] == "Description":
            p[2] = (f"PROFET+2 12V smart high-side power switch, 1 channel, {spec}, "
                    "current sense (IS), PG-TSDSO-14")
        elif p[1] == "ki_keywords":
            p[2] = new.split("-")[0] + " PROFET high side switch"
    return dump(sym, 1) + "\n"


def write_symlib():
    s = '(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "eswitch_gen_libs")\n\t(generator_version "10.0")\n'
    s += sym_fuseholder()
    for name in PROFETS:
        s += sym_bts7008(name)
    s += ")\n"
    os.makedirs(os.path.dirname(SYMLIB), exist_ok=True)
    with open(SYMLIB, "w") as f:
        f.write(s)
    print("wrote", SYMLIB)


if __name__ == "__main__":
    fp_fuseholder()
    fp_screw_terminal_8196()
    fp_terminal_block_16()
    write_symlib()
