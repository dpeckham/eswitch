# eswitch — eight-channel switching bank

**PROTO-PWR3: bare-board prototype fabrication release.** Shared LM74800-Q1
AUTO/logic protection, with passive raw-battery BYPASS selected by one movable
ATO fuse per channel. BYPASS disconnects the PROFET output and has no series
electronics. Move fuses only with power disconnected.

Open **[redesign/eswitch-simple.kicad_pro](redesign/eswitch-simple.kicad_pro)**.
The **212 × 116 mm**, four-layer ESP32-S3 board retains two banks of four channels
at 26 mm pitch and opposite output edges.

- **[JLCPCB upload ZIP](fab/eswitch-simple-jlcpcb-gerbers.zip)**
- [Order settings](redesign/JLCPCB-ORDER.txt) · [Build/assembly notes](redesign/BUILD.md)
- [Full fabrication package](fab/eswitch-simple-fabrication.zip)
- [Portable KiCad project](fab/eswitch-simple-project.zip)
- [One-board DigiKey upload](fab/eswitch-digikey-qty1.csv)
- [BOM](redesign/bom-draft.csv) · [Partial historical cost estimate](redesign/cost-estimate.json)
- [Top view](fab/board-top.png) · [Bottom view](fab/board-bottom.png)
- [Design overview](redesign/README.md) · [Engineering review](redesign/PROTECTION-REVIEW.md)

Native ERC, DRC, connectivity and schematic parity checks pass. The topology model
checks 52,488 mode/supply combinations and 54 isolation cases. Copper-width and
physical layer-transfer checks cover the shared protection and all channels.

This release permits making **first articles for controlled bench testing**.
40 A continuous operation, +80 V surge survival, pump transients and battery-fault
coordination require hardware validation. It is not an installation qualification.
Firmware is not supplied. Follow BUILD.md for initial current-limited testing.

```sh
just verify    # schematic, topology, saved PCB and copper checks
just package   # matched, checked fabrication/project ZIPs and BOM upload
just render    # current board views
```

Native KiCad is discovered on macOS; override with `KICAD_CLI`/`KICAD_PYTHON`.
`redesign/` is authoritative, `fab/` holds the release, `out/` holds disposable
checks and routing candidates. Earlier releases remain in Git history. Do not
order intermediate `out/redesign` boards. Component pricing is incomplete and
historical, not a current cart quote; F10 fasteners are separate purchases.
