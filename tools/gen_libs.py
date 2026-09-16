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
             "https://www.keyelco.com/product.cfm/product_id/1533", ref=(0, -8.6), val=(0, 8.6))


def fp_input_terminal():
    """Wuerth 74650195, drawing 002.002: nine PTH pins; M5 blind thread.

    1.85 mm finished holes at 4.435 mm pitch; recommended 3.2 mm pads.
    All nine pins are the same electrical terminal, not nine current ratings.
    """
    b = ""
    for x in (-4.435, 0.0, 4.435):
        for y in (-4.435, 0.0, 4.435):
            b += tht("1", x, y, 3.2, 1.85)
    b += rect(-5, -5, 5, 5, "F.Fab", 0.1)
    b += circle(0, 0, 4.75, "F.Fab", 0.1)
    b += circle(0, 0, 2.5, "F.Fab", 0.1)
    b += text("M5", 0, -3.6, "F.Fab", 0.7)
    b += rect(-6.55, -6.55, 6.55, 6.55, "F.CrtYd", 0.05)
    write_fp("ScrewTerminal_Wuerth_74650195_M5", b,
             "Wuerth 74650195 REDCUBE THR M5 blind-hole terminal; 9 pins; 85 A at 20 C component rating",
             "screw terminal Wuerth REDCUBE M5 ring lug",
             "https://www.we-online.com/components/products/datasheet/74650195.pdf",
             ref=(0, -7), val=(0, 7))


def fp_terminal_block_16():
    """Two-pole modular direct-entry block; eight interlock into the output row.

    Wuerth 691218410002, drawing 002.002 (2024-01-30): 1 x 0.8 mm pins,
    1.6 mm finished holes, 15.24 x 12.5 x 21.5 mm body. Pin row is 4.6 mm
    from the back, wire entry faces +Y. Interlocking ends share a courtyard
    boundary; the front/back include 0.5 mm for body tolerance and clearance.
    """
    N = 2
    P = 7.62
    b = ""
    for i in range(N):
        b += tht(str(i + 1), i * P, 0.0, 2.6, 1.6)
    x1, x2 = -3.81, (N - 1) * P + 3.81
    b += rect(x1, -4.6, x2, 7.9, "F.Fab", 0.1)
    # No front silkscreen: the wire-entry face deliberately overhangs the PCB.
    b += line(x1, -4.8, x2, -4.8, "F.SilkS", 0.12)
    for i in range(N):
        b += line(i * P - 2.5, 7.9, i * P - 2.5, 4.5, "F.Fab", 0.1)
        b += line(i * P + 2.5, 7.9, i * P + 2.5, 4.5, "F.Fab", 0.1)
        b += circle(i * P, 0.0, 2.3, "F.Fab", 0.1)
    b += line(x1, -4.8, x1, -5.3, "F.SilkS", 0.12)
    b += text("${REFERENCE}", (N - 1) * P / 2, -2.2, "F.Fab", 0.8)
    b += rect(x1, -5.1, x2, 8.4, "F.CrtYd", 0.05)
    write_fp("TerminalBlock_1x02_P7.62mm_Wuerth_2184", b,
             "2-pole direct-entry screw terminal, Wuerth 691218410002, 30 A/pole; interlocking ends share courtyard boundaries",
             "terminal block screw clamp 7.62mm 2 Wuerth 2184 691218410002",
             "https://www.we-online.com/components/products/datasheet/691218410002.pdf",
             ref=(3.81, -6.0), val=(3.81, 9.2))


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
    "BTS7008-1EPR": ("8.8 mOhm typical, 11 A nominal", "infineon-bts7008-1epr-datasheet-en.pdf"),
}


def sym_bts7008(new="BTS7008-1EPR"):
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


def sym_ic(name, footprint, pins, datasheet, prefix="U"):
    """Unstacked, explicitly numbered review symbols; every physical pin is visible."""
    s = f'\t(symbol "{name}"\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
    s += prop("Reference", prefix, 0, 24.13)
    s += prop("Value", name, 0, 21.59)
    s += prop("Footprint", footprint, 0, 0, True)
    s += prop("Datasheet", datasheet, 0, 0, True)
    s += f'\t\t(symbol "{name}_0_1"\n'
    s += '\t\t\t(rectangle (start -10.16 19.05) (end 10.16 -19.05) (stroke (width 0.254) (type default)) (fill (type background)))\n\t\t)\n'
    s += f'\t\t(symbol "{name}_1_1"\n'
    half = (len(pins) + 1) // 2
    for i, (num, label, typ) in enumerate(pins):
        left = i < half
        y = round((half - 1) * 1.27 - (i % half) * 2.54, 4)
        s += pin(typ, -12.7 if left else 12.7, y, 0 if left else 180, 2.54, label, str(num))
    return s + "\t\t)\n\t)\n"


def fp_tpsm63603():
    """TI RDH0030A land pattern, drawing 4226150/B, pp. 42–44.

    Corner L lands use two overlapping rectangles with the same number. No open
    drill in paste pads: thermal vias are placed just outside by the PCB generator.
    """
    name = "TI_RDH0030A_TPSM63603"
    s = FP_HEADER.format(name=name, descr="TI RDH0030A TPSM63603, 4x6mm, 30 lands",
        tags="power module", datasheet="https://www.ti.com/lit/ds/symlink/tpsm63603.pdf",
        refx=0, refy=-4, valx=0, valy=4).replace("(attr through_hole)", "(attr smd)")
    s += rect(-2, -3, 2, 3, "F.Fab", 0.1) + rect(-2.475, -3.4, 2.475, 3.4, "F.CrtYd", 0.05)
    s += line(-1.5, -3.25, 1.5, -3.25, "F.SilkS")
    s += circle(-2.3, -3.25, 0.12, "F.SilkS")
    def pad(n, x, y, w, h):
        return (f'\t(pad "{n}" smd roundrect (at {x} {y}) (size {w} {h}) '
                '(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.1))\n')
    # Left column, top to bottom; right column, bottom to top.
    for n, y in zip(range(2, 8), (-1.775, -.975, -.325, .475, 1.125, 1.775)):
        s += pad(n, -1.775, y, .85, .25)
    for n, y in zip(range(15, 21), (1.775, 1.125, .475, -.325, -.975, -1.775)):
        s += pad(n, 1.775, y, .85, .25)
    for n, x in zip(range(9, 14), (-1, -.5, 0, .5, 1)):
        s += pad(n, x, 2.85, .25, .7)
    for n, x in zip(range(22, 27), (1, .5, 0, -.5, -1)):
        s += pad(n, x, -2.85, .25, .7)
    for n, x, y in ((1, -1.775, -2.425), (8, -1.775, 2.425),
                    (14, 1.775, 2.425), (21, 1.775, -2.425)):
        sx, sy = (-1 if x < 0 else 1), (-1 if y < 0 else 1)
        # Three overlapping rectangles reproduce the stepped corner in 4226150/B:
        # 0.825 wide arm, 0.5 x 0.625 shoulder, 0.25 x 0.95 end-row leg.
        s += pad(n, sx * 1.7875, y, .825, .25)
        s += pad(n, sx * 1.625, sy * 2.5625, .5, .625)
        s += pad(n, sx * 1.5, sy * 2.725, .25, .95)
    s += pad(27, 0, -1.925, 1.25, .74)
    s += pad(28, 0, -.6, 1.6, 1.0)
    s += pad(29, 0, .6, 1.6, 1.0)
    s += pad(30, 0, 1.925, 1.25, .74)
    s += ")\n"
    with open(os.path.join(PRETTY, name + ".kicad_mod"), "w") as f:
        f.write(s)


def fp_kelvin_shunt():
    """CSS4J-4026 manufacturer solder lands, 10.60 x 7.30 mm envelope.

    Power lands 2.55 x 5.60, sense lands 2.55 x .90, .80 mm isolation.
    The inward sense-trace fingers in the drawing are PCB routing, not additional
    solder contacts. Pins 1/3 are one end; 2/4 the other. Never join them on PCB.
    """
    name = "Bourns_CSS4J_4026"
    s = FP_HEADER.format(name=name, descr="Bourns CSS4J-4026 four-terminal Kelvin shunt",
        tags="shunt Kelvin", datasheet="https://bourns.com/docs/product-datasheets/css4j-4026.pdf",
        refx=0, refy=-4.6, valx=0, valy=4.6).replace("(attr through_hole)", "(attr smd)")
    s += rect(-5.03, -3.30, 5.03, 3.30, "F.Fab", .1)
    s += rect(-5.55, -3.9, 5.55, 3.9, "F.CrtYd", .05)
    for n,x,y,w,h in ((1,-4.025,.85,2.55,5.6),(2,4.025,.85,2.55,5.6),
                       (3,-4.025,-3.2,2.55,.9),(4,4.025,-3.2,2.55,.9)):
        s += (f'\t(pad "{n}" smd rect (at {x} {y}) (size {w} {h}) '
              '(layers "F.Cu" "F.Paste" "F.Mask"))\n')
    s += ")\n"
    with open(os.path.join(PRETTY, name + ".kicad_mod"), "w") as f:
        f.write(s)


def write_symlib():
    s = '(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "eswitch_gen_libs")\n\t(generator_version "10.0")\n'
    s += sym_fuseholder()
    for name in PROFETS:
        s += sym_bts7008(name)
    s += sym_ic("LM74800", "Package_SON:WSON-12-1EP_3x3mm_P0.5mm_EP1.5x2.5mm",
        [(n, label, typ) for n, label, typ in (
            (1,"DGATE","output"),(2,"A","input"),(3,"VSNS","input"),(4,"SW","passive"),
            (5,"OV","input"),(6,"EN/UVLO","input"),(7,"GND","power_in"),(8,"HGATE","output"),
            (9,"OUT","input"),(10,"VS","power_in"),(11,"CAP","passive"),(12,"C","input"),
            (13,"RTN_FLOAT","no_connect"))], "https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf")
    power_names = {1:"RT",2:"EN/SYNC",3:"VIN",4:"VIN",5:"PGND",6:"PGND",7:"VOUT",8:"VOUT",
        9:"VOUT",10:"VOUT",11:"SW_NC",12:"VOUT",13:"VOUT",14:"VOUT",15:"VOUT",16:"PGND",17:"PGND",
        18:"VIN",19:"VIN",20:"CBOOT_NC",21:"RBOOT_NC",22:"VLDOIN",23:"VCC",24:"AGND",25:"FB",
        26:"PG",27:"AGND",28:"PGND",29:"PGND",30:"VOUT"}
    types = {"VIN":"power_in", "PGND":"power_in", "AGND":"power_in", "VOUT":"power_out",
             "VCC":"power_out", "PG":"open_collector", "SW_NC":"no_connect"}
    # Multiple VOUT pins share the integrated inductor; only one is an ERC driver.
    s += sym_ic("TPSM63603V3", "eswitch:TI_RDH0030A_TPSM63603",
        [(n, label, "passive" if label == "VOUT" and n != 7 else types.get(label,"input"))
         for n, label in power_names.items()], "https://www.ti.com/lit/ds/symlink/tpsm63603.pdf")
    s += sym_ic("BSC016N06NS", "Package_SON:Infineon_PG-TDSON-8_6.15x5.15mm",
        [(n, "S" if n <= 3 else "G" if n == 4 else "D", "input" if n == 4 else "passive")
         for n in range(1,6)],
        "https://www.infineon.com/assets/row/public/documents/24/49/infineon-bsc016n06ns-datasheet-en.pdf", "Q")
    s += sym_ic("PSMN1R8-80SSE", "Package_TO_SOT_SMD:LFPAK88",
        [(1,"G","input"),(2,"S","passive"),(3,"S","passive"),(4,"S","passive"),(5,"D_MB","passive")],
        "https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf", "Q")
    s += sym_ic("TPS2492", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm",
        [(1,"UVEN","input"),(2,"VREF","output"),(3,"PROG","input"),(4,"TIMER","passive"),
         (5,"OV","input"),(6,"IMON","output"),(7,"GND","power_in"),(8,"PG_N","open_collector"),
         (9,"FLT_N","open_collector"),(10,"NC","no_connect"),(11,"OUT","input"),
         (12,"GATE","output"),(13,"SENSE","input"),(14,"VCC","power_in")],
        "https://www.ti.com/lit/ds/symlink/tps2492.pdf")
    s += sym_ic("Kelvin_Shunt", "eswitch:Bourns_CSS4J_4026",
        [(1,"I_IN","passive"),(3,"S_IN","passive"),(2,"I_OUT","passive"),(4,"S_OUT","passive")],
        "https://bourns.com/docs/product-datasheets/css4j-4026.pdf", "R")
    s += sym_ic("STPS41L60C", "Package_TO_SOT_SMD:TO-263-2",
        [(1,"A1","passive"),(2,"K_TAB","passive"),(3,"A2","passive")],
        "https://www.st.com/resource/en/datasheet/stps41l60c.pdf", "D")
    s += ")\n"
    os.makedirs(os.path.dirname(SYMLIB), exist_ok=True)
    with open(SYMLIB, "w") as f:
        f.write(s)
    print("wrote", SYMLIB)


if __name__ == "__main__":
    fp_fuseholder()
    fp_screw_terminal_8196()
    fp_input_terminal()
    fp_terminal_block_16()
    fp_tpsm63603()
    fp_kelvin_shunt()
    write_symlib()
