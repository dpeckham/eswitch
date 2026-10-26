# Build and fabrication notes — routed prototype

Open `eswitch-simple.kicad_pro` in KiCad 10. The matching schematic and PCB are
authoritative. **Released for prototype fabrication and controlled bench testing.**
Thermal/current ratings and transient/fault behavior have not been bench-qualified.

## Order the prototypes

Upload **`fab/eswitch-simple-jlcpcb-gerbers.zip`** to JLCPCB. Order five bare boards
to cover the planned three manual assemblies and spare first articles. Use:

- Four layers, 176 × 116 mm envelope; retain the supplied antenna corner notch.
- 1.6 mm nominal FR4, **JLC041622-3313**, **2 oz outer AND 2 oz inner** copper.
- ENIG, green soldermask, white silkscreen, electrical test.
- **Epoxy-filled and copper-capped vias** (via-in-pad); minimum via drill 0.30 mm.
- Impedance control: **90 Ω differential ±10%, B.Cu/L4 referenced to In2/L3**;
  USB straight-run width/gap 0.235/0.215 mm. No stackup substitution.
- Bare PCB order; assembly is manual. Keep the full fabrication ZIP for the BOM,
  assembly drawings, paste files, inspection reports and order notes.

`JLCPCB-ORDER.txt` contains the copyable fabrication remarks. The published
stackup's thickness discrepancy below is a CAM clarification, not a reason to
alter the supplied layer geometry or postpone ordering the first articles.

## Mechanical and fabrication

- Outline envelope: **176 × 116 mm**, two banks of four at 26 mm pitch, with outputs
  on opposite edges. The top-left 36 × 6 mm corner is notched to retain the antenna
  overhang. Use the actual Edge.Cuts outline for enclosure design.
- Eight M3 mounting holes, with 4 mm radius copper exclusions. Coordinates in mm
  from the top-left board corner, X rightward and Y downward:
  `(4,38), (4,104), (50,11), (50,104), (172,11), (172,42), (172,74), (172,105)`.
- Four layers: F.Cu / In1.Cu (ground) / In2.Cu / B.Cu. No signal tracks on In1.
- Selected stackup: **JLCPCB JLC041622-3313**, nominal 1.6 mm FR4,
  ENIG, 70 µm modeled outer copper and 61 µm modeled inner copper. Dielectrics
  are 0.1835 / 0.96 / 0.1835 mm. Modeled copper plus dielectric totals 1.689 mm;
  JLCPCB's current public template also lists 1.589 mm compressed thickness.
  Preserve the named stackup and resolve this discrepancy in the CAM stackup,
  rather than changing dielectric dimensions to force the sum. Both figures are
  within nominal 1.6 mm ±10%. See `jlc-stackup-evidence.json` (checked 2026-10-26).
- Minimum track 0.18 mm, clearance 0.20 mm, via diameter 0.50 mm, drilled via
  0.30 mm, copper-to-edge 0.40 mm. Signal routes use 0.18–0.20 mm traces.
- USB pair is on B.Cu with a reserved In2 ground reference. Its retained
  0.235 mm width / 0.215 mm straight-run gap targets 90 Ω differential using
  the earlier stackup calculator result. Specify 90 Ω differential ±10% impedance
  control, L4 referenced to L3; do not permit a stackup substitution.
- Battery feeds occupy reserved F.Cu and In2 corridors. Signal routing protects
  these corridors and designated outer-layer ground returns. LOAD uses F.Cu/In2/B.Cu.
- See `power-copper-review.json` for connected-path erosion widths and VS copper
  areas. The screen exempts terminal landing regions and models pads as solid;
  it does not qualify pad annuli, plated barrels, contact resistance or ampacity.
  Validate junction temperature, layer sharing and connector heating on hardware.
- Heavier outer copper (3–4 oz) is a possible later fabrication choice, not a
  substitute for this geometry rework. Confirm etching clearances, via plating,
  finished thickness and USB impedance before changing the modeled stackup.

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
- **Changed output wiring:** J11–J18 pin 1 is LOAD+, pin 2 is GND. Check the new
  silkscreen before wiring; polarity is reversed relative to the compact board.
- The clip hole-row pitches are 13.47 mm (AUTO–COM) and 9.27 mm (COM–BYPASS).
  SW is oriented opposite COM/LOAD. The AUTO pitch agrees with Keystone drawing
  3557 rev F's 13.46 mm nominal within 0.01 mm; the 9.27 mm BYPASS pitch uses two
  clips in the same orientation. The custom BYPASS arrangement still needs a
  physical first-article fit check. Fit the fuse in both positions before soldering
  the clips; round holes do not key orientation. Do not force a misaligned fuse.
- Maximum channel fuses: **10 / 10 / 5 / 5 / 5 / 5 / 5 / 20 A**. F9 logic fuse:
  **2 A maximum**. Provide an installation-level upstream battery fuse.
- Use TLA431AIDBZR for U14; ordinary TL431 is not an approved substitution because
  the clamp rail has capacitive loading. The clamp nominal is 2.495 V.
- Order **epoxy-filled and copper-capped vias (via-in-pad process)**, including
  exposed-pad thermal vias and the four upper-bank clamp-pad vias. Ordinary
  soldermask plugging/tenting is not an equivalent process. Preserve all component
  PTH and mounting NPTH openings. Review solder-paste coverage with the assembler.
  Twelve 0.3 mm-drill vias per exposed pad connect to branch VS, never ground.
  The filled/capped process controls solder wicking; it does not qualify thermal
  performance. Confirm the paste pattern and reflow profile on the first assembly.
- Four upper-bank clamp ground pads also contain small plated vias. Include these
  in the via-in-pad process review; account for solder wicking and pad flatness.
- Agree a reflow assembly process for the REDCUBE terminals and heavy copper;
  do not assume the existing manual-assembly plan is sufficient for these parts.
- Maintain antenna clearance beyond the board edge and clearance beneath bottom
  components when selecting the enclosure and standoffs.

## Verification status

### Intended prototype installation

- Reported source: Vatrer 300 Ah LiFePO4 battery, charged by a Victron Orion XS
  12/12-70A DC–DC charger; no direct alternator connection to the service battery.
- Reported upstream protection: Blue Sea Systems 40 A MRBF on the eswitch feed,
  with a separate Blue Sea Systems 75 A MRBF on the charger branch. Exact fuse
  part numbers are not yet recorded. Do not treat 40 A as a fault-current
  ceiling or assume series coordination with the onboard branch fuses.
- The Orion XS output is adjustable from 10 to 17 V. Use the battery manufacturer's
  charging profile within this board's 16 V operating ceiling; charger capability
  is not evidence that a 17 V setting is acceptable for this board.
- Prototype fabricator: JLCPCB. Select 2 oz outer **and** 2 oz inner copper;
  default 0.5 oz inner copper does not match the power-layout assumptions.
  The exact heavy-copper stackup is now selected and listed by JLCPCB; CAM acceptance
  and the finished impedance remain manufacturer checks.

- Reported motor load: Rule 1500 GPH bilge pump. Rule's standard 12 V models
  02, 02-6 and 04 specify a 10 A fuse and 4 A at 12 V / 4.8 A at 13.6 V. This is a
  provisional match, not identification of the installed pump or its startup
  current. Reserve CH1 or CH2 with a 10 A fuse for that standard 12 V pump.
  Confirmed one-way distances are 1 m battery-to-board and 3 m board-to-pump.
  Proposed conductors: **8 AWG (8.37 mm²) copper positive and negative for the
  battery feed**, and **4 mm² copper positive and negative for the pump**.
  Use stranded copper cable with insulation/installation ampacity suitable for
  the respective 40 A and 10 A fuses; do not substitute copper-clad aluminium.
  The estimated combined wire-only drop at 40 A common / 4.8 A pump current is
  0.289 V at 20°C copper and 0.351 V at 75°C copper. Fuse, terminal, PCB and pump
  pigtail drops are additional. These cable sizes are not a battery-operation
  release; see the unresolved fuse coordination below and `installation-screen.json`.

Sources: [Victron 70 A technical data](https://www.victronenergy.com/media/pg/Orion_XS_12-12-70A_DC-DC_Battery_Charger/en/technical-data.html),
[JLCPCB copper weights](https://jlcpcb.com/help/article/jlcpcb-copper-weight).
[Rule standard pump table](https://www.xylem.com/siteassets/brand/rule/resources/technical-brochure/standard-bilge-pumps-model-number-table.pdf).

The 2026-10-26 manufacturer review also found that the Littelfuse 287 ATOF branch
fuses have a 1 kA interrupting rating at 32 VDC. Battery fault-current assessment
must cover **all nine fuses**, not only F9. The MRBF's 40 A current rating and the
battery BMS's continuous-current rating are not bounds on prospective fault
current. A tested series combination or a conservative fault-current bound is
needed before claiming coordination; neither has yet been established.

The hardware is frozen for this prototype order, including the existing 2 A
0466002.NR logic fuse and SMCJ16A TVSs. Battery-fault coordination and transient
performance remain open; no component protection claim has been upgraded merely
by changing release status. Use a current-limited bench source for initial tests.

Native KiCad ERC, PCB DRC and schematic/PCB parity reports are in `out/redesign`
in the source repository. The saved layout has zero DRC violations, zero
unconnected nets and zero schematic-parity findings. The power-terminal graph
checks cover 13,122 mode/switch combinations and 24 fault/removal cases.

These are connectivity/layout checks, not transient simulation or bench results.
The 40 A aggregate target and maximum fuse values are not qualified continuous
load ratings. Follow the electrical work list in `README.md`, particularly
backfeed/power-down injection, inductive loads, thermal rise and fuse coordination.
USB bench use remains battery-disconnected. Correct-polarity 9.5–16 V operation
is the agreed scope; there is no electronic reverse-polarity/overvoltage disconnect.

## First-article test sequence

1. **Unpowered fit/inspection:** check board dimensions, mounting and antenna
   clearance; dry-fit all fuse clips, both fuse positions, terminal wires and
   standoffs. Check polarity and soldering before applying power.
2. **Logic only:** remove all eight channel fuses and disconnect USB. Apply 12 V
   from a current-limited supply, initially 0.1 A; check for abnormal current or
   heating before raising the limit to 0.5 A for ESP32 startup. Verify 3V3 and the
   2.495 V clamp rail. A brownout at the lower limit is not by itself a fault.
   Test USB separately with the battery/bench input disconnected.
3. **One channel:** start with a small resistive load and a low-rated branch fuse
   within the channel maximum. Test AUTO, BYPASS and fuse-removed OFF; change fuse
   position only unpowered. Firmware is not supplied: use reviewed test firmware
   or a controlled fixture to exercise IN/DEN and record IS/ADC readings.
4. **Pump:** after the resistive tests, use the actual 3 m pump harness, a 10 A fuse
   on CH1/CH2 and the pump manufacturer's wet-test procedure. Capture startup
   current and VS/OUT transients during switching. Start with single-channel tests;
   do not infer surge energy from the fuse rating or the 4.8 A running current.
5. **Thermal ramp:** use dummy loads, increase one channel at a time, then combine
   loads. Log ambient, terminal/fuse/PROFET/PCB temperatures and voltage drops.
   At each step wait for temperature stabilization; stop for unexpected heating,
   protection trips, discoloration or unstable rails. For initial screening use
   conservative stop points of 30°C rise at contacts and 80°C measured package/PCB
   surface temperature. These are test stop points, not qualified operating limits
   or inferred junction temperatures. Do not jump directly to the 40 A target.
6. **Fault qualification is separate:** do not use the 300 Ah battery to conduct
   deliberate short-circuit or TVS-failure tests on these first articles. Direct
   battery fault safety requires the documented coordination work above.

Record findings and photographs against the PCB hash in the package manifest;
feed measured problems into the next revision instead of treating this prototype
as a production-approved installation.

## Cost

Recorded-price subtotal: $104.04 for one board or $92.76 per board for three sets,
including eight standoffs but excluding the unpriced U14, PCB fabrication,
assembly and additional installation hardware. See `cost-estimate.json`.
