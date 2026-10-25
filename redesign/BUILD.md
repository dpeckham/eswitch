# Build and fabrication notes — routed prototype

Open `eswitch-simple.kicad_pro` in KiCad 10. The matching schematic and PCB are
authoritative. This is a prototype layout release; thermal/current ratings and
transient/fault behavior have not been bench-qualified.

## Mechanical and fabrication

- Outline: **136 × 104 mm**, two banks of four with outputs on opposite edges.
  Dimension objects are on `Dwgs.User`. PCB area is 31.1% below the 228 × 90 mm layout.
- Eight M3 mounting holes, with 4 mm radius copper exclusions. Coordinates in mm
  from the top-left board corner, X rightward and Y downward:
  `(4,32), (4,98), (50,5), (50,98), (132,5), (132,36), (132,68), (132,99)`.
- Four layers: F.Cu / In1.Cu (ground) / In2.Cu / B.Cu. No signal tracks on In1.
- Heavy-copper stackup retained from the earlier design: nominal 1.6 mm FR4,
  ENIG, 70 µm modeled outer copper and 61 µm modeled inner copper. Dielectrics
  are 0.1835 / 0.96 / 0.1835 mm. Modeled copper plus dielectric totals 1.689 mm;
  agree finished thickness and material tolerances with the fabricator.
- Minimum track 0.18 mm, clearance 0.20 mm, via diameter 0.50 mm, drilled via
  0.30 mm, copper-to-edge 0.40 mm. Actual signal routes primarily use 0.20 mm.
- USB pair is on B.Cu with a reserved In2 ground reference. Its retained
  0.235 mm width / 0.215 mm straight-run gap targets 90 Ω differential using
  the earlier stackup calculator result; confirm against the production stackup.
- Selected signal routes cross the In2 raw-battery and CH1/2/5/6 output spreaders.
  The front raw-battery path remains protected, and the outer output paths remain
  connected. Local LED escapes indent the back output spreaders. The conservative
  DC screen credits only front copper for the battery path.
- The compact design has less VS heat-spreader copper. See
  `compact-copper-review.json` for filled-area comparisons and sampled raw-spine
  widths. Validate PROFET junction temperature, current sharing and connector
  temperature rise at the retained current targets on hardware.

The fabrication ZIP includes four copper Gerbers, soldermask, silkscreen, paste,
outline, separate plated/non-plated drill files, drill maps, placement CSV,
assembly SVGs, dimension SVG, BOM, checks and a SHA-256 manifest.

## Assembly

- Most small components, the ESP32 module, USB and power electronics are on B.Cu;
  fuse clips, battery studs, output terminals and LEDs are on F.Cu. Placement
  coordinates use KiCad's board origin in mm; bottom placement rotation and
  orientation must follow the assembler's convention. The bottom assembly SVG
  is mirrored for viewing that side.
- Custom 3D models for clips and terminals are simplified envelopes, not supplier
  manufacturing models. Use the BOM part numbers and footprint drawings.
- Fit **one** ATO blade fuse per channel across the middle and AUTO clips for
  normal operation. Move that same fuse to middle/BYPASS for direct fused battery
  power, or remove it for OFF. Disconnect battery power before moving fuses.
- Maximum channel fuses: **10 / 10 / 5 / 5 / 5 / 5 / 5 / 20 A**. F9 logic fuse:
  **2 A maximum**. Provide an installation-level upstream battery fuse.
- Use TLA431AIDBZR for U14; ordinary TL431 is not an approved substitution because
  the clamp rail has capacitive loading. The clamp nominal is 2.495 V.
- Review solder-paste coverage and exposed-pad via wicking with the assembler.
  Thermal vias connect to branch VS; do not connect them to ground.
- Maintain antenna clearance beyond the board edge and clearance beneath bottom
  components when selecting the enclosure and standoffs.

## Verification status

Native KiCad ERC, PCB DRC and schematic/PCB parity reports are in `out/redesign`
in the source repository. The released layout has zero DRC violations, zero
unconnected nets and zero schematic-parity findings. The power-terminal graph
checks cover 13,122 mode/switch combinations and 24 fault/removal cases.

These are connectivity/layout checks, not transient simulation or bench results.
The 40 A aggregate target and maximum fuse values are not qualified continuous
load ratings. Follow the electrical work list in `README.md`, particularly
backfeed/power-down injection, inductive loads, thermal rise and fuse coordination.
USB bench use remains battery-disconnected. Correct-polarity 9.5–16 V operation
is the agreed scope; there is no electronic reverse-polarity/overvoltage disconnect.

## Cost

Recorded-price subtotal: $104.04 for one board or $92.76 per board for three sets,
including eight standoffs but excluding the unpriced U14, PCB fabrication,
assembly and additional installation hardware. See `cost-estimate.json`.
