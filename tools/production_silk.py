"""Legible revision-B silk without exposed-pad or adjacent-outline collisions."""
import argparse
from pathlib import Path
import pcbnew
import design
from gen_pcb import V, fuse_silk_labels
from pcb_io import save_board


def apply_silk(board):
    detached = []
    for ref in ("SW1", "C2", "C17"):
        board.FindFootprintByReference(ref).Reference().SetVisible(False)
    for n in range(1, 9):
        fp = board.FindFootprintByReference(f"U{n}")
        x = pcbnew.ToMM(fp.GetPosition().x)
        fp.Reference().SetPosition(V(x+4, 39.8))
        fp.Reference().SetTextSize(V(.8, .8))
        fp.Reference().SetTextThickness(pcbnew.FromMM(.12))
    for ref, x, y in (("U10", 12, 23.6), ("U11", 13, 56.6), ("U9", 32, 37.8)):
        board.FindFootprintByReference(ref).Reference().SetPosition(V(x, y))
    for item in board.GetDrawings():
        if item.GetClass() == "PCB_TEXT" and item.GetText() == "LOGIC MAX 2A":
            _, x, y, _, _, _ = fuse_silk_labels()[-1]
            item.SetPosition(V(x, y))
    for ref in design.OUTPUT_REFS:
        fp = board.FindFootprintByReference(ref)
        x, y = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
        for shape in fp.GraphicalItems():
            if shape.GetLayer() != pcbnew.F_SilkS or shape.GetClass() != "PCB_SHAPE":
                continue
            start = (pcbnew.ToMM(shape.GetStart().x), pcbnew.ToMM(shape.GetStart().y))
            end = (pcbnew.ToMM(shape.GetEnd().x), pcbnew.ToMM(shape.GetEnd().y))
            for point, setter in ((start, shape.SetStart), (end, shape.SetEnd)):
                px, py = point
                if abs(px-(x-3.81)) < .00001:
                    setter(V(x-3.66, py))
                elif abs(px-(x+11.43)) < .00001:
                    setter(V(x+11.28, py))
    module = board.FindFootprintByReference("U9")
    y = pcbnew.ToMM(module.GetPosition().y)
    for shape in module.GraphicalItems():
        if shape.GetLayer() == pcbnew.B_SilkS and shape.GetClass() == "PCB_SHAPE" and shape.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            start = (pcbnew.ToMM(shape.GetStart().x), pcbnew.ToMM(shape.GetStart().y))
            end = (pcbnew.ToMM(shape.GetEnd().x), pcbnew.ToMM(shape.GetEnd().y))
            if all(abs(point[1]-(y-3.25)) < .00001 for point in (start, end)):
                shape.SetStart(V(start[0], y-3.55))
                shape.SetEnd(V(end[0], y-3.55))
    module = board.FindFootprintByReference("U10")
    module.SetFPID(pcbnew.LIB_ID("eswitch", "ESP32-S3-WROOM-1_Edge"))
    for shape in list(module.GraphicalItems()):
        if (shape.GetLayer() != pcbnew.B_SilkS or shape.GetClass() != "PCB_SHAPE"
                or shape.GetShape() != pcbnew.SHAPE_T_SEGMENT):
            continue
        a, b = shape.GetStart(), shape.GetEnd()
        ax, ay, bx, by = a.x, a.y, b.x, b.y
        edge = pcbnew.FromMM(.5)
        if max(ay, by) < edge:
            module.Remove(shape)
            detached.append(shape)
        elif min(ay, by) < edge:
            assert ax == bx, "Review nonvertical outline before clipping"
            shape.SetStart(pcbnew.VECTOR2I(ax, max(ay, edge)))
            shape.SetEnd(pcbnew.VECTOR2I(bx, max(by, edge)))
    return detached


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, required=True)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board.resolve()))
    detached = apply_silk(board)
    save_board(args.board, board)
