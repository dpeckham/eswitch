"""Minimal S-expression reader/writer for KiCad files."""
from __future__ import annotations
import re


class Sym(str):
    """A bare (unquoted) symbol token."""
    __slots__ = ()

    def __repr__(self):
        return f"Sym({str.__repr__(self)})"


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def parse(text: str):
    """Parse text into nested lists. Strings stay str, bare tokens become Sym."""
    pos = 0
    stack = [[]]
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            done = stack.pop()
            stack[-1].append(done)
        elif m.group(3) is not None:
            stack[-1].append(m.group(3).replace('\\"', '"').replace("\\\\", "\\"))
        elif m.group(4) is not None:
            stack[-1].append(Sym(m.group(4)))
    if len(stack) != 1:
        raise ValueError("unbalanced parentheses")
    return stack[0]


def parse_one(text: str):
    items = parse(text)
    if len(items) != 1:
        raise ValueError(f"expected one top-level expression, got {len(items)}")
    return items[0]


def _fmt_atom(a) -> str:
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, bool):
        return "yes" if a else "no"
    if isinstance(a, int):
        return str(a)
    if isinstance(a, float):
        s = f"{a:.6f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    s = str(a).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def dump(node, indent: int = 0) -> str:
    """Serialize a nested list in KiCad's tab-indented style."""
    if not isinstance(node, list):
        return _fmt_atom(node)
    if not node:
        return "()"
    has_sub = any(isinstance(c, list) for c in node)
    tab = "\t" * indent
    if not has_sub:
        return "(" + " ".join(_fmt_atom(c) for c in node) + ")"
    parts = []
    head = []
    i = 0
    while i < len(node) and not isinstance(node[i], list):
        head.append(_fmt_atom(node[i]))
        i += 1
    out = "(" + " ".join(head)
    for c in node[i:]:
        if isinstance(c, list):
            out += "\n" + tab + "\t" + dump(c, indent + 1)
        else:
            out += " " + _fmt_atom(c)
    out += "\n" + tab + ")"
    return out


def find(node, key: str):
    """First child list whose head symbol == key."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(node, key: str):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def S(*items):
    """Build a list, turning plain str heads into Sym automatically."""
    out = []
    for i, it in enumerate(items):
        if i == 0 and isinstance(it, str) and not isinstance(it, Sym):
            out.append(Sym(it))
        else:
            out.append(it)
    return out
