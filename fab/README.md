# Current compact prototype

These files all describe the **136 × 104 mm** board in
[`../redesign/eswitch-simple.kicad_pro`](../redesign/eswitch-simple.kicad_pro).

- `eswitch-simple-fabrication.zip`: Gerbers, drills, assembly/placement files,
  BOM, dimensions, native layout check and source/file checksums.
- `eswitch-simple-project.zip`: portable current KiCad project and local assets.
- `board-top.png`, `board-bottom.png`: current board renders.

Regenerate packages with `just package` and views with `just render`.
See [`../redesign/BUILD.md`](../redesign/BUILD.md) for assembly and the outstanding
electrical/thermal qualification. Older releases are available through Git history.
