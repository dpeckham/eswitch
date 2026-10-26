# eswitch — eight-channel switching bank

Open **[redesign/eswitch-simple.kicad_pro](redesign/eswitch-simple.kicad_pro)**.
This is the worktree's only KiCad project: a **176 × 116 mm**, four-layer
ESP32-S3 board with two banks of four solid-state channels and one movable
AUTO/BYPASS blade fuse per channel.

- [Design and verification status](redesign/README.md)
- [Build, assembly and fabrication notes](redesign/BUILD.md)
- [BOM](redesign/bom-draft.csv) · [Component cost estimate](redesign/cost-estimate.json)
- [Current fabrication package](fab/eswitch-simple-fabrication.zip)
- [JLCPCB Gerber upload ZIP](fab/eswitch-simple-jlcpcb-gerbers.zip)
- [Portable project package](fab/eswitch-simple-project.zip)
- [Top view](fab/board-top.png) · [Bottom view](fab/board-bottom.png)

The power-layout rework reserves two-layer battery feeds and outer-layer ground
returns. See the source-hashed connected-copper screen in
`redesign/power-copper-review.json`. ERC, DRC, schematic parity and the connected-copper
regression checks pass. **Released for prototype fabrication and controlled bench
testing.** The 40 A aggregate target, battery-fault coordination and transient
performance remain unqualified. Fit the fuse clips and test the hardware on the
first articles; see the ordering settings and bring-up steps in the build notes.

## Commands

```sh
just verify     # schematic, connectivity model and saved PCB checks
just package    # checked fabrication and portable-project ZIPs in fab/
just render     # current board views in fab/
```

Native KiCad is discovered on macOS; use `KICAD_CLI` and `KICAD_PYTHON` to override
its executables. `redesign/` holds the active design, `fab/` only its current
deliverables, and `out/` disposable checks/tool dependencies. `tools/` and `lib/`
contain shared generator/routing support. `docs/` retains the historical pricing
evidence used by the current cost estimate.

Earlier tracked revisions remain available through Git history. The stale local
rev-A Gerbers were quarantined under `out/obsolete-fabrication/`, outside `fab/`.
