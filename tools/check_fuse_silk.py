#!/usr/bin/env python3
"""Check circuit/fuse identity on the saved PCB. Run with KiCad's Python."""
import pcbnew
import argparse

import design
from gen_pcb import OUT_PCB, V, fuse_silk_labels
from revision_c import CX


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", default=OUT_PCB)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(args.board)
    text = [item for item in board.GetDrawings() if item.GetClass() == "PCB_TEXT"]
    expected = [(f'CH{n} MAX FUSE {design.CHANNELS[n][0]}A',CX[n-1]+10.6,100,pcbnew.F_SilkS,.8,90)
                for n in range(1,9)] + [fuse_silk_labels()[-1]]
    expected=[(*item[:4],max(1.0,item[4]),item[5]) for item in expected]
    assert len(expected) == 9, "Eight branch fuses plus the logic fuse"
    for content, x, y, layer, size, rot in expected:
        matches = [item for item in text if item.GetText() == content]
        assert len(matches) == 1, (content, "missing or duplicate label")
        item = matches[0]
        assert item.GetPosition() == V(x, y), content
        assert item.GetLayer() == layer, content
        assert item.IsMirrored() == (layer == pcbnew.B_SilkS), content
        assert item.GetTextSize() == V(size, size), content
        assert item.GetTextAngleDegrees() == rot, content
    for n, (rating, _, _) in design.CHANNELS.items():
        assert board.FindFootprintByReference(f"F{n}"), n
        assert f"CH{n} MAX FUSE {rating}A" in [item.GetText() for item in text]
        assert not any(item.GetText() == f"CH{n} {rating}A" for item in text), n
    assert board.FindFootprintByReference("F9").GetValue() == "2A 1206"
    print("Fuse silk: eight circuit numbers and maximum ratings + 2 A logic fuse verified")


if __name__ == "__main__":
    main()
