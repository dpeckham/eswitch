# Revision C — released for prototype fabrication

Upload **[eswitch-revC-gerbers.zip](eswitch-revC-gerbers.zip)** for bare PCBs.
The **[complete build package](eswitch-revC-build-package.zip)** contains the
schematic, 1:1 assembly drawings, BOM, cost breakdown, engineering limits and
verification evidence. Revision-B packages are withdrawn.

The revised board is **334 × 172 mm**. All eight channels have independent
hardware latches ahead of both AUTO and BYPASS. USB edge alignment, exposed-pad
thermal vias, input source vias, twelve mounting holes with hardware clearances,
Kelvin sensing, monitoring, local reset buttons and test points are included.

## Order settings

| Setting | Required value |
|---|---|
| Board | FR-4, four layers, 334 × 172 mm, single PCB |
| Quantity | Five bare PCBs is the offered batch covering three planned assemblies |
| Thickness | 1.6 mm nominal; JLC041622-3313 stackup |
| Copper | **2 oz outer AND inner** |
| Finish / mask / legend | ENIG 1 µin / green / white |
| USB impedance | 90 Ω differential, ±10%; supplied USB-impedance-request.jpg |
| Via covering | Plugged for eligible closed-mask vias only; preserve exposed thermal pads |
| Min via selection | 0.3 mm hole / 0.4–0.45 mm diameter offered option |
| Production files | Confirm Production File = Yes; **disable automatic confirmation** |
| Electrical test | Flying Probe Fully Test |
| Mark | Remove Mark |
| Assembly / stencil | Not ordered; manual assembly plan in build package |

Use the exact layer order F.Cu / In1.Cu / In2.Cu / B.Cu. Preserve separate
PTH/NPTH drills and all supplied pad/mask openings. Read `gerbers/README-fab.txt`
for the complete specification. JLC can reset finish and stackup settings after
an upload: check these values **after** uploading. Approve the manufacturer's
production files manually, including any proposed USB impedance adjustments.

## Checks and remaining qualification

KiCad 10.0.6 ERC, DRC including warnings, unrouted connections and schematic/PCB
parity all pass with zero findings. The native 1195-pin map, fuse geometry and
silkscreen, mounting clearances and 3276 USB reference samples pass. All 29
bounded startup/fault transient cases pass. These are calculations and simulation,
not measurements of an assembled board.

Independent Gerber/Excellon parsing verifies four copper layers, the outline,
1579 plated drill objects and 14 non-plated holes. Exported copper/mask/silk and
top/bottom 3D views were inspected. [CAM evidence](cam-review.json) binds the
final flat upload ZIP to the inspected export; the build ZIP contains a manifest
of every included file and the approved source hashes.

JLC's public parser recognized four layers and 334 × 172 mm and produced top/bottom
previews; [final upload/settings evidence](jlc-upload-review.json) records the exact
upload hash and [configured quote](jlc-configured-quote.png). Its detailed Gerber
viewer requires sign-in. Manufacturer engineering
DFM and production-file approval remain part of the actual order; neither is
claimed as completed here. No cart, order or purchase was submitted.

Assemble and validate one board first. The 40 A aggregate continuous target and
marine installation are not qualified until the documented fault/recovery,
regulator/USB, thermal and mechanical tests pass. See the build package's
`prototype-release.md` and `bring-up.md`.

## Cost, USD observed 2026-09-19

| Purchase | Cost |
|---|---:|
| Exact BOM for one assembly, including fuses and 12 standoffs | $318.40 |
| Optional one-board cart with explicit spares at cheaper price breaks | $299.30 |
| Exact parts for three assemblies | $800.31 total; **$266.77 each** |
| Configured JLC bare-board estimate, five PCBs | $224.39 total |
| Three exact BOM sets plus five bare PCBs | $1,024.70 total; $341.57 per assembly with two spare PCBs |

The PCB figure includes 2 oz on all four layers, ENIG, impedance control and
production-file confirmation. It is an online estimate, subject to manufacturer
file review, not a reserved quote. Shipping, tax, tariffs, assembly, solder/paste
and enclosure-specific screws/washers are excluded. The import BOM remains for
**one assembly**; apply the intended build quantity when purchasing.

[Detailed BOM pricing](../../docs/bom-cost.md) ·
[One-board import BOM](../digikey/eswitch-digikey-bom.csv) ·
[Three-board cost breakdown](../digikey/cost-three-board-build.csv) ·
[Authoritative release status](../../docs/release-status.json)
