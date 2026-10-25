# eswitch — compact eight-channel switching bank

Open **[redesign/eswitch-simple.kicad_pro](redesign/eswitch-simple.kicad_pro)**.
This is the worktree's only KiCad project: a routed **136 × 104 mm**, four-layer
ESP32-S3 board with two banks of four solid-state channels and one movable
AUTO/BYPASS blade fuse per channel.

- [Design and verification status](redesign/README.md)
- [Build, assembly and fabrication notes](redesign/BUILD.md)
- [BOM](redesign/bom-draft.csv) · [Component cost estimate](redesign/cost-estimate.json)
- [Current fabrication package](fab/eswitch-simple-fabrication.zip)
- [Portable project package](fab/eswitch-simple-project.zip)
- [Top view](fab/board-top.png) · [Bottom view](fab/board-bottom.png)

The saved board passes native KiCad ERC, DRC and schematic parity checks with
zero violations or unconnected nets. Electrical/thermal bench qualification of
the 40 A aggregate target remains open.

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

Old layouts, releases and backups have been removed from this worktree; earlier
tracked revisions remain available through Git history.
