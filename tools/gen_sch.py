#!/usr/bin/env python3
"""Generate eswitch.kicad_sch (single flat A2 sheet) plus project/lib-table files.

Every pin gets a short wire stub ending in a net label; GND / +3V3 / +12V use power
symbols where the stub is vertical. Unused visible pins get no-connect flags.
"""
import os
import sys
import uuid
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexp import parse_one, dump, find, find_all, Sym, S  # noqa: E402
import kicad_env  # noqa: E402
import design  # noqa: E402

PROJECT = "eswitch"
SCH_VERSION = 20250114
ROOT_UUID = "8d2c1f0e-5a7b-4c3d-9e1f-eswitch00001"
STUB = 2.54
POWER_UP = {"+3V3": "power:+3V3", "+12V": "power:+12V", "VBUS": "power:VBUS"}
POWER_DOWN = {"GND": "power:GND"}
STRIP_TOKENS = {"show_name", "do_not_autoplace", "in_pos_files", "duplicate_pin_numbers_are_jumpers",
                "embedded_fonts"}

_uuid_counter = [0]


def uid():
    _uuid_counter[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"eswitch-sch-{_uuid_counter[0]}"))


# ------------------------------------------------------------------ library symbols
_symcache = {}


def _sanitize(node):
    """Convert a KiCad 10 lib symbol node into one accepted by the 9.0 schematic parser."""
    if not isinstance(node, list):
        return node
    out = []
    for c in node:
        if isinstance(c, list) and c and c[0] in STRIP_TOKENS:
            continue
        out.append(_sanitize(c))
    if out and out[0] == "power":
        return [Sym("power")]
    return out


def load_symbol(lib_id):
    """Return the lib symbol node, flattened (extends resolved), renamed to lib_id."""
    if lib_id in _symcache:
        return _symcache[lib_id]
    lib, name = lib_id.split(":", 1)
    if lib == "eswitch":
        doc = parse_one(open(os.path.join(ROOT, "lib", "eswitch.kicad_sym")).read())
        sym = next(s for s in find_all(doc, "symbol") if s[1] == name)
    else:
        doc = parse_one(open(kicad_env.symbol_file(lib, name)).read())
        sym = next(s for s in find_all(doc, "symbol") if s[1] == name)
    ext = find(sym, "extends")
    if ext:
        parent = load_symbol(f"{lib}:{ext[1]}")
        # copy parent, override properties with the child's, keep parent's graphics/pins
        merged = [c for c in parent if not (isinstance(c, list) and c and c[0] == "property")]
        props = {p[1]: p for p in find_all(parent, "property")}
        for p in find_all(sym, "property"):
            props[p[1]] = p
        merged = merged[:2] + list(props.values()) + merged[2:]
        sym = merged
    sym = _sanitize(sym)
    base = name

    def rename(n):
        if isinstance(n, list):
            if n and n[0] == "symbol" and isinstance(n[1], str):
                n[1] = lib_id if n[1] == base else n[1]
            for c in n:
                rename(c)
    rename(sym)
    sym[1] = lib_id
    if not find(sym, "extends"):
        pass
    _symcache[lib_id] = sym
    return sym


def symbol_pins(sym):
    """[(number, name, x, y, angle, length, hidden, type)] from all sub-units."""
    pins = []
    for sub in find_all(sym, "symbol"):
        for p in find_all(sub, "pin"):
            at = find(p, "at")
            num = find(p, "number")[1]
            name = find(p, "name")[1]
            hide = find(p, "hide")
            hidden = bool(hide and hide[1] == "yes")
            pins.append((str(num), name, float(at[1]), float(at[2]), int(float(at[3])), float(find(p, "length")[1]),
                         hidden, str(p[1])))
    return pins


def rot_vec(dx, dy, rot):
    """Rotate a screen vector (y down) counter-clockwise by rot degrees."""
    r = rot % 360
    if r == 0:
        return dx, dy
    if r == 90:
        return dy, -dx
    if r == 180:
        return -dx, -dy
    if r == 270:
        return -dy, dx
    raise ValueError(rot)


def pin_screen(part, pin):
    """Connection point and outward unit direction of a pin on the sheet."""
    _, _, x, y, ang, _, _, _ = pin
    dx, dy = rot_vec(x, -y, part.rot)
    ox, oy = -math.cos(math.radians(ang)), math.sin(math.radians(ang))  # outward, screen coords
    ox, oy = rot_vec(ox, oy, part.rot)
    return (round(part.at[0] + dx, 4), round(part.at[1] + dy, 4)), (round(ox), round(oy))


# ------------------------------------------------------------------ writers
def prop(key, val, x, y, hide=False, justify=None, rot=0):
    eff = [S("font", S("size", 1.27, 1.27))]
    if justify:
        eff.append(S("justify", Sym(justify)))
    if hide:
        eff.append(S("hide", Sym("yes")))
    return S("property", key, val, S("at", x, y, rot), S("effects", *eff))


def text_pos(sym, key, at, rot):
    """Sheet position/rotation of a library property (Reference/Value) for a placed part."""
    for p in find_all(sym, "property"):
        if p[1] == key:
            a = find(p, "at")
            dx, dy = rot_vec(float(a[1]), -float(a[2]), rot)
            trot = (int(float(a[3])) + rot) % 180
            return (round(at[0] + dx, 4), round(at[1] + dy, 4), trot)
    return (at[0] + 2.54, at[1], 0)


def symbol_instance(lib_id, ref, value, footprint, at, rot, pins, extra_fields=None, datasheet="", desc="",
                    hide_value=False, sym=None):
    x, y = at
    node = S("symbol", S("lib_id", lib_id), S("at", x, y, rot), S("unit", 1),
             S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes")), S("on_board", Sym("yes")),
             S("dnp", Sym("no")), S("uuid", uid()))
    rx, ry, rr = text_pos(sym, "Reference", at, rot) if sym else (x + 2.54, y - 2.54, 0)
    vx, vy, vr = text_pos(sym, "Value", at, rot) if sym else (x + 2.54, y, 0)
    node.append(prop("Reference", ref, rx, ry, hide=ref.startswith("#"), rot=rr))
    node.append(prop("Value", value, vx, vy, hide=hide_value, rot=vr))
    node.append(prop("Footprint", footprint, x, y, hide=True))
    node.append(prop("Datasheet", datasheet, x, y, hide=True))
    node.append(prop("Description", desc, x, y, hide=True))
    for k, v in (extra_fields or {}).items():
        node.append(prop(k, v, x, y, hide=True))
    for num in pins:
        node.append(S("pin", num, S("uuid", uid())))
    node.append(S("instances", S("project", PROJECT, S("path", "/" + ROOT_UUID, S("reference", ref), S("unit", 1)))))
    return node


def wire(p1, p2):
    return S("wire", S("pts", S("xy", p1[0], p1[1]), S("xy", p2[0], p2[1])),
             S("stroke", S("width", 0), S("type", Sym("default"))), S("uuid", uid()))


def label(name, at, direction):
    """Local label whose text extends away from the wire end in `direction` (dx,dy)."""
    dx, dy = direction
    if dx > 0:
        rot, just = 0, "left bottom"
    elif dx < 0:
        rot, just = 180, "right bottom"
    elif dy < 0:
        rot, just = 90, "left bottom"
    else:
        rot, just = 270, "right bottom"
    j = S("justify", *[Sym(t) for t in just.split()])
    return S("label", name, S("at", at[0], at[1], rot), S("effects", S("font", S("size", 1.27, 1.27)), j),
             S("uuid", uid()))


def text(s, at, size=2.0, rot=0):
    return S("text", s, S("exclude_from_sim", Sym("no")), S("at", at[0], at[1], rot),
             S("effects", S("font", S("size", size, size), S("bold", Sym("yes"))), S("justify", Sym("left"), Sym("bottom"))),
             S("uuid", uid()))


def no_connect(at):
    return S("no_connect", S("at", at[0], at[1]), S("uuid", uid()))


def main():
    parts = design.build()
    items = []
    lib_symbols = S("lib_symbols")
    used = {}
    pwr_count = [0]

    def ensure(lib_id):
        if lib_id not in used:
            sym = load_symbol(lib_id)
            used[lib_id] = sym
            lib_symbols.append(sym)
        return used[lib_id]

    def power_symbol(lib_id, net, at):
        ensure(lib_id)
        pwr_count[0] += 1
        ref = f"#PWR{pwr_count[0]:03d}"
        node = symbol_instance(lib_id, ref, net, "", at, 0, ["1"], sym=used[lib_id])
        items.append(node)

    for part in parts:
        sym = ensure(part.lib_id)
        pins = symbol_pins(sym)
        desc = ""
        ds = ""
        for p in find_all(sym, "property"):
            if p[1] == "Description":
                desc = p[2]
            elif p[1] == "Datasheet":
                ds = p[2]
        hide_value = part.ref.startswith("#")
        items.append(symbol_instance(part.lib_id, part.ref, part.value, part.footprint, part.at, part.rot,
                                     [p[0] for p in pins], part.fields, ds, desc, hide_value, sym))
        if part.ref.startswith("#FLG"):
            # PWR_FLAG: stub down to a label
            (px, py), _ = pin_screen(part, pins[0])
            end = (px, py + STUB)
            items.append(wire((px, py), end))
            items.append(label(part.pins["1"], end, (0, 1)))
            continue
        seen_pos = set()
        for pin in pins:
            num, name, _, _, _, _, hidden, ptype = pin
            (px, py), (ox, oy) = pin_screen(part, pin)
            net = part.pins.get(num)
            if net is None:
                if hidden or ptype == "no_connect" or (px, py) in seen_pos:
                    continue
                items.append(no_connect((px, py)))
                continue
            if (px, py) in seen_pos:
                continue  # stacked pins share the connection
            seen_pos.add((px, py))
            end = (round(px + ox * STUB, 4), round(py + oy * STUB, 4))
            items.append(wire((px, py), end))
            if net in POWER_DOWN and (ox, oy) == (0, 1):
                power_symbol(POWER_DOWN[net], net, end)
            elif net in POWER_UP and (ox, oy) == (0, -1):
                power_symbol(POWER_UP[net], net, end)
            else:
                items.append(label(net, end, (ox, oy)))

    # annotations
    for n in range(1, design.N_CH + 1):
        c, r = (n - 1) % 4, (n - 1) // 4
        bx, by = 12.7 + c * 72.39, 22.86 + r * 82.55
        items.append(text(f"CHANNEL {n}", (bx, by - 1.27), 2.5))
    items.append(text("MCU: ESP32-S3-WROOM-1  (IS1-8 -> ADC1 IO1,2,4-9; IN1-8 -> IO10-14,21,47,48; DEN -> IO38; STAT LED -> IO41)",
                      (330.2, 34.29), 2.0))
    items.append(text("POWER: +12V -> F9 -> D1 -> VIN <- D2 <- USB VBUS;  TPS54360B 500 kHz buck -> +3V3", (330.2, 226.06), 2.0))
    items.append(text("I/O: J1 load terminals (odd=LOAD+, even=GND), J2/J3 #10 screw terminals", (330.2, 328.93), 2.0))
    items.append(text("8-channel PROFET+2 (BTS7008-1EPP) 12 V load switch with 3-position ATO fuse bypass", (12.7, 12.7), 3.5))

    doc = S("kicad_sch", S("version", SCH_VERSION), S("generator", "eeschema"), S("generator_version", "9.0"),
            S("uuid", ROOT_UUID), S("paper", "A2"),
            S("title_block", S("title", "eswitch - 8ch PROFET load switch"), S("date", "2026-09-13"),
              S("rev", "A"), S("company", "dpeckham")),
            lib_symbols, *items,
            S("sheet_instances", S("path", "/", S("page", "1"))),
            S("embedded_fonts", Sym("no")))
    out = os.path.join(ROOT, f"{PROJECT}.kicad_sch")
    with open(out, "w") as f:
        f.write(dump(doc) + "\n")
    print("wrote", out, f"({len(items)} items, {len(used)} lib symbols)")

    write_tables()


def write_tables():
    with open(os.path.join(ROOT, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "eswitch")(type "KiCad")(uri "${KIPRJMOD}/lib/eswitch.kicad_sym")(options "")(descr "eswitch project symbols"))\n)\n')
    with open(os.path.join(ROOT, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n  (lib (name "eswitch")(type "KiCad")(uri "${KIPRJMOD}/lib/eswitch.pretty")(options "")(descr "eswitch project footprints"))\n)\n')
    pro = os.path.join(ROOT, f"{PROJECT}.kicad_pro")
    if not os.path.exists(pro):
        import json
        tmpl = os.path.join(kicad_env.share_dir(), "template", "kicad.kicad_pro")
        data = json.load(open(tmpl))
        data.setdefault("meta", {})["filename"] = f"{PROJECT}.kicad_pro"
        json.dump(data, open(pro, "w"), indent=2)
        print("wrote", pro)


if __name__ == "__main__":
    main()
