#!/usr/bin/env python3
"""Generate simple VRML (.wrl) 3D bodies for the project footprints (lib/eswitch.3dshapes).

KiCad VRML convention: 1 unit = 2.54 mm, X = footprint X, Y = -footprint Y, Z = height.
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "lib", "eswitch.3dshapes")
S = 1 / 2.54

BRASS = (0.85, 0.75, 0.45)
TIN = (0.80, 0.80, 0.78)
STEEL = (0.60, 0.60, 0.62)
GREEN = (0.12, 0.50, 0.22)
BLUE = (0.20, 0.45, 0.90)
DARK = (0.15, 0.15, 0.15)


class Wrl:
    def __init__(self):
        self.shapes = []

    def box(self, x1, x2, fy1, fy2, z1, z2, color):
        """Axis-aligned box; fy are footprint-Y (down) values."""
        y1, y2 = -fy2, -fy1
        p = [(x1, y1, z1), (x2, y1, z1), (x2, y2, z1), (x1, y2, z1),
             (x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.shapes.append((p, f, color))

    def cyl(self, cx, fcy, r, z1, z2, color, n=24):
        cy = -fcy
        p = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), z1) for i in range(n)]
        p += [(x, y, z2) for (x, y, _) in p]
        f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            f.append((i, j, n + j, n + i))
        self.shapes.append((p, f, color))

    def write(self, name):
        out = ["#VRML V2.0 utf8", f"# eswitch generated model {name}"]
        for p, f, c in self.shapes:
            pts = " ".join(f"{x * S:.4f} {y * S:.4f} {z * S:.4f}," for x, y, z in p)
            idx = " ".join(" ".join(str(i) for i in face) + " -1," for face in f)
            out.append("Shape { appearance Appearance { material Material { diffuseColor %.2f %.2f %.2f "
                       "specularColor 0.3 0.3 0.3 shininess 0.3 } } geometry IndexedFaceSet { solid FALSE "
                       "coord Coordinate { point [ %s ] } coordIndex [ %s ] } }" % (c[0], c[1], c[2], pts, idx))
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, name + ".wrl"), "w") as fh:
            fh.write("\n".join(out) + "\n")
        print("wrote", name + ".wrl")


def fuseholder():
    w = Wrl()
    P = 9.27
    for blade, off in ((-P, -2.1), (0.0, 2.1), (P, 2.1)):
        y1, y2 = (blade - 1.8, blade + 2.9) if off > 0 else (blade - 2.9, blade + 1.8)
        w.box(-1.9, 1.9, y1, y2, 0.0, 10.2, TIN)
        w.box(-1.9, -1.5, y1, y2, 10.2, 10.6, TIN)   # top lips
        w.box(1.5, 1.9, y1, y2, 10.2, 10.6, TIN)
    # ATO fuse in the AUTO position (body 19.1 x 5.1 x 18.8, blades 5.2 x 0.8)
    yc = -P / 2
    w.box(-2.55, 2.55, yc - 9.55, yc + 9.55, 8.0, 26.8, BLUE)
    for blade in (-P, 0.0):
        w.box(-0.4, 0.4, blade - 2.6, blade + 2.6, 2.0, 8.0, TIN)
    w.write("Fuseholder_ATO_3pos_Keystone_3557")


def screw_terminal_8196():
    w = Wrl()
    w.box(-6.0, 6.0, -6.0, 6.0, 0.0, 12.0, BRASS)
    w.cyl(0.0, 0.0, 4.75, 12.0, 14.8, STEEL)      # 10-32 binding head screw
    w.box(-3.6, 3.6, -0.5, 0.5, 14.8, 15.3, DARK)  # slot
    w.write("ScrewTerminal_Keystone_8196_10-32")


def terminal_block_16():
    # Conservative body envelope, not a manufacturer's detailed mechanical model.
    w = Wrl()
    N, P = 2, 7.62
    x1, x2 = -3.81, (N - 1) * P + 3.81
    w.box(x1, x2, -4.6, 7.9, 0.0, 21.3, GREEN)
    for i in range(N):
        x = i * P
        w.cyl(x, 0.0, 2.3, 21.3, 21.5, STEEL)
        w.box(x - 2.5, x + 2.5, 7.9, 8.0, 3.0, 10.0, DARK)
    w.write("TerminalBlock_1x02_P7.62mm_Wuerth_2184")


def input_terminal():
    # Body envelope only; M5 screw and lug stack are installation hardware.
    w = Wrl()
    w.box(-5, 5, -5, 5, 0.5, 6.5, TIN)
    for x in (-4.435, 0, 4.435):
        for y in (-4.435, 0, 4.435):
            w.box(x - 0.75, x + 0.75, y - 0.75, y + 0.75, -3.0, 0.5, TIN)
    w.cyl(0, 0, 2.5, 6.5, 6.51, DARK)
    w.write("ScrewTerminal_Wuerth_74650195_M5")


if __name__ == "__main__":
    fuseholder()
    screw_terminal_8196()
    input_terminal()
    terminal_block_16()
