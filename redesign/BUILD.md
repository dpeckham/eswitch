# PROTO-PWR3 build and fabrication

## Order the bare PCB

Upload **`fab/eswitch-simple-jlcpcb-gerbers.zip`** to JLCPCB. Five bare boards
cover three planned manual assemblies and two spares.

- Four layers, **212 × 116 mm** envelope. Use supplied Edge.Cuts; the top-left
  antenna notch is **72 × 6 mm** after adding the 36 mm protection strip.
- FR4, nominal 1.6 mm, **JLC041622-3313** stackup, **2 oz outer AND inner copper**.
- ENIG, green mask, white silk, electrical test.
- **Epoxy-filled and copper-capped vias**, including all via-in-pad locations.
  Soldermask plugging/tenting is not equivalent. Keep component PTH and NPTH open.
- Minimum via drill 0.30 mm; require at least **20 µm finished hole copper**.
- USB **90 Ω differential ±10%**, B.Cu/L4 referenced to In2/L3; straight-pair
  width/gap 0.235/0.215 mm. No unreviewed stackup/copper-weight substitutions.
- Minimum routed track 0.18 mm, clearance 0.20 mm, via diameter 0.50 mm,
  copper-to-edge 0.40 mm. Bare-board order; assembly is separate.

JLC's published JLC041622-3313 response gives 1.589 mm compressed thickness;
the modeled copper/dielectric sum is 1.689 mm. Both lie within nominal 1.6 mm ±10%.
Ask CAM to confirm the exact stackup and finished thickness rather than altering
the dielectrics to force a sum. See `jlc-stackup-evidence.json` and
`JLCPCB-ORDER.txt` for the copyable remarks.

The full fabrication ZIP includes Gerbers, separate plated/non-plated drills,
drill maps, placement, paste, assembly/dimension SVGs, BOM, engineering checks and
SHA-256 manifest. The Gerber ZIP is the upload file; the project ZIP is editable.

## Mechanical assembly

Eight M3 mounting holes, coordinates in mm from board origin, X right/Y down:
`(34,112), (40,104), (86,11), (86,104), (208,11), (208,42), (208,74), (208,105)`.
Use the actual outline for enclosure design and standoffs that clear bottom parts.
Preserve the ESP32 antenna overhang and clearance.

Most logic/PROFET parts are on B.Cu. The protection MOSFETs, clips, terminals and
indicator LEDs include top-side parts. Use the placement file and assembly SVGs;
the bottom assembly drawing is mirrored for viewing that side. Simplified 3D
models are envelopes, not supplier manufacturing drawings. Check heavy-copper
reflow/paste and terminal-pin solder fill with the assembler.

### F10 shared fuse

Fit one Mersen **FR14GG50V40**, two **G098170 / MR14SPRING** clips and two Würth
**74650195** terminals. Terminal centers are 86 mm apart; inward-facing clip
centers are 42 mm apart. The fuse/clip envelope is 100 × 20.7 mm.

Purchase two **M5 × 6 socket-head screws**, M5 flat washers (about **5.3 mm ID,
10 mm OD**), and flat shims separately. The washers must span the clips' 6.5 mm
holes. Measure clip-tab plus washer/shim thickness and target approximately
**3 mm thread engagement** without bottoming in the nominal 4 mm blind thread.
For a 6 mm screw this means approximately 3 mm total clamped stack. Do not use
the screw head directly on the oversized hole. Würth's specified torque is
**2.2 N·m**; support the terminal during tightening rather than twisting its solder
joints. Dry-align clips with an unpowered fuse before tightening. Check extraction,
clip-to-board clearance and contact heating on the first assembly. Allow at least
30 mm assembly height plus tool/extraction clearance.

### Channel selectors

Fit three Keystone 3557 clips and **one ATO fuse per channel**. The middle clip
is LOAD; one side is AUTO/PROFET OUT, the other RAW/BYPASS. Move the fuse only with
**battery and USB disconnected**. Remove for OFF. Fuse maxima are
**10 / 10 / 5 / 5 / 5 / 5 / 5 / 20 A**. F9 is **2 A maximum**, F10 is 40 A.

Clip hole-row pitches are 13.47 mm AUTO–LOAD and 9.27 mm LOAD–RAW. The first pair
uses opposite clip orientation; the second uses the same orientation. Fit a fuse
in both positions before soldering; round holes do not key the orientation.
Do not force a misaligned fuse. J11–J18 pin 1 is LOAD+, pin 2 GND.

### Electronics details

- C27: **1 µF 50 V**, not the earlier 100 nF candidate.
- D8/D9: current `_A-08` MPNs from the BOM, not obsolete TR3 codes.
- R104–R804: high-power **ERJ-PA3** sense resistors; do not substitute ordinary
  0.1 W 0603 parts just because resistance/size match.
- U14: **TLA431AIDBZR**; ordinary TL431 is not an approved capacitive-load substitution.
- U15 exposed pad floats; do not tie it to GND. PROFET exposed-pad vias connect
  to AUTO_PROTECTED, not ground. Retain all filled/capped via-in-pad locations.
- USB and 3.3 V UART are for battery-disconnected bench use. Firmware must set
  all channels OFF at startup and must not automatically retry a latched fault.
- Indicators and shunts are on PROFET outputs. They do not indicate or measure BYPASS.

## Bench bring-up and installation

The design-file checks permit making first articles. They do not qualify the
assembled unit for unattended service or establish a continuous 40 A rating.
See `PROTECTION-REVIEW.md` for calculations, sources and exact limitations.

1. Unpowered: check dimensions, all clip/fuse fits, screw engagement, polarity,
   soldering, terminal stability and standoff clearance.
2. Remove channel fuses; fit F9/F10. Use a current-limited 12 V bench source,
   initially 0.1 A, then up to 0.5 A for logic startup after checking for abnormal
   consumption. Measure protected rail, 3V3 and 2.495 V clamp rail. Test USB
   separately with battery input disconnected.
3. Use a small resistive load and suitable low-rated fuse. Test AUTO/BYPASS/OFF,
   with all mode changes unpowered. Verify BYPASS with F10 removed and MCU absent.
4. Scope protection startup/cutoff/recovery, including a loaded recovery, and
   effective C27 capacitance. Ramp toward +80 V with controlled energy and no
   BYPASS loads; initially test unloaded, then dummy loads. Hold for 5 s and verify
   cutoff without blowing a fuse. Capture fast-edge overshoot separately.
5. Wet-test the actual pump/harness only after resistive checks. Log startup,
   turn-off and negative-output transients. Increase channel/aggregate dummy
   loads gradually while recording MOSFET, terminal, fuse and PCB temperatures.
   Measure voltage drop at each protection device to detect unequal sharing.
6. Verify sense fault reporting, clamp rail and power-down injection. Never infer
   load current from an ADC reading saturated by the fault clamp.
7. Record battery/fuse model and fault-current coordination before direct-battery
   installation. ATO 32 V / 1 kA ratings and F9's interruption rating are not
   upgraded by the upstream MRBF. Raw BYPASS receives surges/reverse polarity.

Installation wiring: **8 AWG stranded copper positive and negative**, 1 m each,
for the 40 A MRBF board feed; **4 mm² positive and negative**, 3 m each, to the pump.
The separate Orion XS 12/12-70A charger branch retains its 75 A MRBF. Use the battery
manufacturer's charging profile within 9.5–16 V board operation. The provisional
standard 12 V Rule 1500 GPH pump uses CH1/2 with a 10 A fuse; confirm the actual model.
Wire-only drop at 40 A common/4.8 A pump is estimated at 0.289 V (20°C copper),
0.351 V (75°C); terminal, fuse, PCB and pump-pigtail drops are additional.

Electronics-fault recovery: disconnect all power, remove F10, put usable channel
fuses in BYPASS, then restore power. An upstream fuse may also need replacement
after isolating the fault. Shared terminal/copper damage is not covered by this
recovery procedure. BYPASS continuity is never inhibited by the protection circuit.
