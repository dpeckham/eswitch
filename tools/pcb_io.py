"""Crash-resistant writes for generated and routed KiCad boards."""
import os
from pathlib import Path
import tempfile

import pcbnew


def save_board(path, board):
    """Serialize to a sibling, sync it, then atomically replace the destination."""
    target = Path(path).resolve()
    fd, temporary = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=".kicad_pcb", dir=target.parent)
    os.close(fd)
    try:
        if not pcbnew.SaveBoard(temporary, board):
            raise RuntimeError(f"KiCad could not save {temporary}")
        from fabrication_rules import ensure_stackup
        temporary_path = Path(temporary)
        serialized = temporary_path.read_text()
        updated = ensure_stackup(serialized)
        if updated != serialized:
            temporary_path.write_text(updated)
        with open(temporary, "rb") as stream:
            if os.fstat(stream.fileno()).st_size < 100:
                raise RuntimeError("Refusing to replace a board with empty output")
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        board.SetFileName(str(target))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
        # KiCad may create a project sidecar while serializing. Its randomized
        # name belongs exclusively to this save, never to the user's project.
        sidecar = Path(temporary).with_suffix(".kicad_pro")
        if sidecar.exists():
            sidecar.unlink()
