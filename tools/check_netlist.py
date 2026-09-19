#!/usr/bin/env python3
"""Compare a KiCad s-expression netlist against tools/design.py connectivity."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse_one, find, find_all  # noqa: E402
import design  # noqa: E402


def read_netlist(path):
    doc = parse_one(open(path).read())
    nets = {}
    for net in find_all(find(doc, "nets"), "net"):
        name = find(net, "name")[1].lstrip("/")
        nodes = set()
        for node in find_all(net, "node"):
            nodes.add((find(node, "ref")[1], str(find(node, "pin")[1])))
        nets[name] = nodes
    return nets


def main(path):
    design.build()
    doc = parse_one(open(path).read())
    components = {find(c, "ref")[1]: c for c in find_all(find(doc, "components"), "comp")}
    for part in design.PARTS:
        if not part.footprint:
            continue
        comp = components[part.ref]
        assert find(comp, "value")[1] == part.value, (part.ref, "stale schematic value")
        assert find(comp, "footprint")[1] == part.footprint, (part.ref, "stale schematic footprint")
        fields = {find(f, "name")[1]: f[2] if len(f) > 2 else ""
                  for f in find_all(find(comp, "fields"), "field")}
        for key in ("MPN", "Manufacturer"):
            if part.fields.get(key):
                assert fields.get(key) == part.fields[key], (part.ref, "stale schematic", key)
    want = {n: {x for x in s if not x[0].startswith("#")} for n, s in design.nets().items()}
    got = read_netlist(path)
    # stacked hidden OUT pins of the PROFET all land on LOAD; accept them
    ok = True
    for name, pins in want.items():
        gp = got.get(name)
        if gp is None:
            # maybe KiCad named it differently (e.g. label vs power); search by membership
            cands = [n for n, s in got.items() if pins <= s]
            if len(cands) == 1:
                gp = got[cands[0]]
                print(f"note: net {name} appears as {cands[0]}")
            else:
                print(f"MISSING net {name}: {sorted(pins)}")
                ok = False
                continue
        extra = {p for p in gp - pins if not (p[0].startswith("U") and p[0][1:].isdigit() and int(p[0][1:]) <= 8
                                               and p[1] in {"9", "10", "12", "13", "14"})}
        missing = pins - gp
        if missing or extra:
            ok = False
            print(f"MISMATCH {name}: missing={sorted(missing)} extra={sorted(extra)}")
    # any nets in KiCad with >1 node not covered by design (accidental shorts / dangling)
    covered = set(want)
    for name, s in got.items():
        if name not in covered and len(s) > 1 and not name.startswith("unconnected"):
            print(f"UNEXPECTED net {name}: {sorted(s)}")
            ok = False
    print("netlist", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
