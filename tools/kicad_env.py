"""Locate KiCad's bundled symbol/footprint libraries.

Works both inside `kicad python3.11` (AppImage) and outside it; falls back to
the extracted AppImage tree or an explicit env var.
"""
import os
import glob

_CANDIDATES = []
for var in ("KICAD_SYMBOL_DIR_OVERRIDE", "KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR"):
    if os.environ.get(var):
        _CANDIDATES.append(os.path.dirname(os.environ[var]))
if os.environ.get("KICAD_STOCK_DATA_HOME"):
    _CANDIDATES.append(os.environ["KICAD_STOCK_DATA_HOME"])
_CANDIDATES += glob.glob("/tmp/.mount_kicad*/share/kicad")
_CANDIDATES += ["/tmp/squashfs-root/share/kicad", "/usr/share/kicad"]


def share_dir() -> str:
    for c in _CANDIDATES:
        if os.path.isdir(os.path.join(c, "symbols")) and os.path.isdir(os.path.join(c, "footprints")):
            return c
    raise RuntimeError("KiCad share dir not found; set KICAD_STOCK_DATA_HOME")


def symbol_file(lib: str, name: str) -> str:
    """Path of a single-symbol file (KiCad 10 .kicad_symdir layout) or the lib file."""
    base = os.path.join(share_dir(), "symbols")
    p = os.path.join(base, lib + ".kicad_symdir", name + ".kicad_sym")
    if os.path.exists(p):
        return p
    p = os.path.join(base, lib + ".kicad_sym")
    if os.path.exists(p):
        return p
    raise FileNotFoundError(f"symbol {lib}:{name}")


def footprint_lib_dir(lib: str) -> str:
    return os.path.join(share_dir(), "footprints", lib + ".pretty")
