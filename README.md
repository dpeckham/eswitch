# eswitch — eight-channel house-bank load switch

ESP32-S3 controlled high-side switch with one ATO fuse per channel. Each three-clip
holder accepts a fuse in AUTO (through the PROFET) or BYPASS (direct to the load).

The main KiCad project contains the **334 × 172 mm revision-C design**, with an
independent hardware latch in each channel ahead of both fuse positions. A short
is handled locally; healthy outputs and logic retain their shared supply. See
[circuit and limits](docs/channel-isolation-review.md), the authoritative
[release status](docs/release-status.json), and [BOM cost per board](docs/bom-cost.md).

**Revision C is released for prototype fabrication.** Use the
[bare-board upload ZIP](fab/revision-c/eswitch-revC-gerbers.zip) and
[complete build package](fab/revision-c/eswitch-revC-build-package.zip).
[Order settings and release evidence](fab/revision-c/README.md) accompany them.
ERC, DRC including warnings, routing and schematic parity are all clean;
29 transient cases pass. Bench qualification remains required before service.

The revision-B fabrication release is withdrawn. Its historical ZIP does not
implement the new fault-isolation requirement.

| Item | Requirement |
|---|---|
| Supply | 9.5–16 V; nominal 12 V house bank |
| Simultaneous load | 40 A continuous target, not a qualified rating |
| Channels | CH1–2: 10 A fuse maximum; CH3–7: 5 A; CH8: 20 A |
| Main fuse | Upstream protection; no onboard main fuse; F9 is logic-only, maximum 2 A |
| Outputs | Eight Wuerth 691218410002 direct-entry blocks; pin 1 GND, pin 2 LOAD+ |
| Inputs | Two Wuerth 74650195 M5 ring-lug terminals |
| PCB | 334 × 172 mm, JLCPCB JLC041622-3313, four layers, 2 oz outer/inner, 1.6 mm nominal, ENIG |
| Assembly | Three boards, manual paste + hot air/hot plate; validate one first |
| Procurement | Exact DigiKey MPNs; dated stock is not a reservation and must be refreshed |

Fuse labels identify circuit numbers and maximum fuse values, not guaranteed
continuous currents. USB is for initial bench programming **with battery power
disconnected**; subsequent updates are OTA. Mixed AUTO/BYPASS startup is required.
See [agreed scope](docs/design-constraints.md); deferred installation details have
not been silently assumed.

```sh
mise install
mise exec -- just verify          # saved schematic/PCB; ERC, DRC, parity, pin/silk/geometry checks
mise exec -- just all             # verify + renders; preserves completed routing
mise exec -- just review-package  # clearly unreleased CAM/BOM/schematic/assembly drawing ZIP
mise exec -- just bom             # requires fresh stock evidence; fails when stale
mise exec -- just package         # also requires engineering release for these exact source hashes
python3 -m unittest discover -s tools -p 'test_*.py'
```

`out/verification/manifest.json` binds verification results to the exact source
files and report hashes, including the engineering release documents. The
withdrawn prototype ZIP is retained under `fab/revision-b/` for traceability.
`out/review/` retains an unreleased review snapshot; do not upload it.
`fab/legacy-f76c39e/` and the old OSH Park upload are obsolete.
No order or purchase has been made.

The saved PCB is the authoritative routed design. `just pcb` now creates an
**unrouted candidate under out/**. `just libs` and `just sch` are explicit source
regeneration operations. Checked finish/routing tools replace the old revision-A
coordinate patches in the build recipes. Do not run legacy `finish.py`/`stitch.py`
on revision C. Its one-time migration uses the explicitly saved revision-B snapshot.

[Assembly instructions](docs/assembly.md) · [Channel/input protection](docs/channel-isolation-review.md)
· [Critical review/history](docs/critical-review.md) · [Per-board BOM](fab/digikey/eswitch-digikey-bom.csv)
