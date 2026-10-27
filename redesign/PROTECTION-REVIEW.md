# PWR3 prototype engineering review — 2026-10-27

## Disposition

Design-file review supports making **bare-board first articles for controlled
bench testing**. This is not a claim of 40 A continuous operation, 80 V surge
qualification, battery-fault coordination, or approval for unattended bilge service.
Those require the assembled hardware. The fabrication checks must pass on the
exact exported board; intermediate `out/redesign` candidates are not releases.

## Architecture and static protection

- F10 supplies only AUTO/logic. BYPASS is raw battery through the movable ATO fuse.
  Its continuity does not depend on F10, either controller, any semiconductor, or
  firmware. The selector disconnects PROFET OUT from LOAD in BYPASS/OFF.
- LM74800-Q1 follows TI SNOSD95C section 10.3, common-source topology with OV
  sensing the **input**. It cuts off instead of dissipating the several-second
  surge in a linear pass stage. The design target is +80 V, not the TI example's
  200 V qualification. Do not apply 80 V to connected BYPASS loads.
- Nominal trip is 16.841 V; tolerance screen gives 16.299–17.386 V rising and
  14.878–15.906 V falling. The reference's exposed pad floats. EN has no MCU
  dependency. `protection_topology.py` checks all 52,488 modeled combinations and
  54 shared-fuse isolation cases, including a deliberately incorrect backfeed case.
- Four 200 V IPT067N20NM6 high-side MOSFETs provide substantial static VDS margin
  at 80 V. Two 60 V BSC016N06NS devices are on the protected side. Gate ratings
  exceed the controller's 15 V absolute maximum differential gate drive.
- The 4.7 kΩ/2 W feed and 51 V zener do not rely on F10 opening. At 80 V the
  nominal resistor/zener powers are 0.179/0.315 W. For any clamp voltage between
  0 and 80 V, available zener power is at most 0.358 W with -5% resistor tolerance.
  The conditional 150°C clamp estimate is 59.823 V, below the controller's 65 V
  operating limit. At assumed 150 K/W and 85°C ambient the conservative power
  bound gives 138.8°C junction. Actual board thermal impedance and bias-dependent
  voltage must be measured; this is not a worst-case transient guarantee.
- D8/D9 use current ordering codes `BZG03B51-M3_A-08` and `BZG03C82-M3_A-08`.
  D9 is retained from the reference's differential clamp concept; its nominal
  82 V value alone does not establish the controller's 85 V differential limit
  over temperature. Positive 80 V cutoff is the target; no extended negative
  surge or 200 V rating is claimed.
- D6/D7 follow TI's SMBJ150A + SMBJ33CA series arrangement. They are **not** the
  element intended to clamp an 80 V plateau. D10 is a local SMCJ16A protected-rail
  suppressor. Overshoot and inductive energy remain waveform-dependent.

## Startup, SOA and sharing

- C27 was increased from 100 nF to **1 µF, 50 V X7R**. TI's recommendation is
  at least ten times combined Ciss: 4 × 7.3 nF + 2 × 6.5 nF = 42.2 nF, therefore
  422 nF effective pump capacitance. Confirm at least 422 nF at the operating
  differential voltage (up to 15 V), including bias/tolerance/temperature.
- High-bank Qg/max-source-current screening gives approximately 11 ms. This is
  not a gate-slew or SOA simulation. IN and DEN have local OFF bias at cold boot,
  so first power-up should charge the electronics with all channel loads OFF.
  Firmware must initialize all channels OFF before intentionally enabling them.
- A recovery with GPIOs already asserted can be a loaded start. Test it separately
  with dummy loads. Do not use the total gate-charge time as the MOSFET's linear
  conduction duration or assume fourfold SOA from four parallel parts.
- Individual 10 Ω gate resistors reduce parasitic interaction. Shared gate drive
  does not guarantee sharing during linear operation. Max 25°C RDS(on) predicts
  3.96 W total MOSFET conduction loss at 40 A with equal sharing; hot resistance,
  layout resistance and contact loss are additional. The first articles must
  measure each device's temperature and voltage drop during ramp and restart.
- Scope an input rise to 80 V with controlled source energy and no BYPASS loads,
  capture input/common-source/protected output/VS and both gate-source voltages,
  then hold for **5 seconds**. Repeat unloaded before increasing dummy-load current.
  Verify cutoff without fuse operation and check recovery without repeated
  thermal cycling or uncontrolled fault retry. Fast-edge overshoot is a distinct
  test from the plateau. Inductive-load tests follow, using the actual harness.

## Copper and physical layer changes

- `power_geometry.py` applies explicit PWR3 regression floors to 60 paths.
  LOAD paths must retain at least 4 mm on both F.Cu and In2; raw channel feeds
  at least 7 mm on F.Cu; the input-to-F10 corridor at least 7.8 mm on In2.
  Protected channel branches must retain 4.5 mm on In2. PROFET output paths
  retain at least 3 mm front and 4 mm rear. The principal ground plane retains
  at least 5.8 mm from battery return to each output. These are prototype geometry
  minima, **not current ratings**. Pad landings are exempt from erosion.
- `power_transitions.py` checks actual SMD-side copper and transfer vias reaching
  another connected layer: 12 per protection MOSFET, 12 per PROFET supply land,
  eight per PROFET output, plus TVS and logic-feed transfers. It does not count
  a projected SMD position on an inner pour as a connection.
- With assumed 20 µm hole plating and full 1.689 mm barrel length, equal-sharing
  barrel resistance is approximately 0.097 mΩ per 12 × 0.4 mm array, 0.129 mΩ
  per 12 × 0.3 mm array, and 0.145 mΩ per eight × 0.4 mm array. Thermal spreading,
  contact resistance, annular necks and unequal current sharing are not included.
  Specify at least 20 µm finished hole copper and inspect the first article.
- F10/battery terminals use nine soldered pins each; channel clips have two pins.
  These joints carry current as well as plated barrels. Verify wetting and solder
  fill, especially with heavy copper. No thermal performance is inferred from DRC.

## Sense outputs

Normal-current conversion remains 2.2 kΩ / BTS7004, 3.3 kΩ / BTS7008 and
1.2 kΩ / BTS7002. Published-point tolerance bounds are below 2.5 V.
The 10 mA maximum IS fault current can overrun the original 0.1 W sense resistor
rating. R104–R804 now use Panasonic ERJ-PA3 high-power 0603 parts at the same
resistance and footprint. The screen conservatively uses 0.25 W at 70°C,
derated to 155°C, and checks 85°C ambient. With the 4.7 kΩ ADC series resistor
and a 3.25 V active-clamp assumption, sense/series resistor dissipation is recorded
per channel in `sense-screen.json`. The independent TLA431 clamp rail sinks fault
current instead of dumping it into 3V3. Verify clamp voltage and power-down
injection on the real board; firmware must not report clamped fault readings as
valid load current. BYPASS current is not measured.

## F10 mounting review

- Fuse: Mersen FR14GG50V40, 40 A, 14 × 51 mm; manufacturer lists 250 VDC,
  100 kA at L/R = 15 ms. This is the fuse component rating, not an assembly rating.
- Two G098170 MR14SPRING clips (63 A), mounted on two Würth 74650195 M5 terminals.
  Mersen's drawing specifies **86 mm mounting pitch**, giving **42 mm clip-center
  pitch**. Footprint matches the terminal's nine-pin grid: 8.87 mm overall pitch,
  1.85 mm finished holes and 3.2 mm pads. The layout reserves 100 × 20.7 mm.
- Würth's terminal drawing specifies 2.2 N·m tightening torque and a blind M5
  thread. Do not substitute the rejected PF-KB1 clip assembly requiring 4.5 ± 1 N·m.
- Prototype hardware: two M5 × 6 socket-head machine screws; M5 flat washers with
  approximately 5.3 mm ID and 10 mm OD, spanning the 6.5 mm clip holes; additional
  flat shims as needed. Measure actual clip-tab and washer stack before tightening:
  target **3 mm screw engagement**, without bottoming in the nominal 4 mm thread.
  With a 6 mm screw, total tab+washer+shim thickness is therefore approximately
  3 mm. Do not clamp a fuse clip using the screw head alone. Hardware is purchased
  separately from the electronic BOM.
- Align clips using an unpowered fuse before final tightening; support the terminals
  while applying torque, never twist the solder joints. Ensure the clip bodies are
  clear of the PCB and the fuse can be removed. Allow at least 30 mm above the PCB
  for the assembly plus extraction/tool clearance. A transparent insulating cover
  over live clips is appropriate in the enclosure. Dry fit and contact heating are
  first-article tests, not prerequisites for producing the bare PCB.

## Evidence and remaining hardware tests

Sources: [TI LM7480-Q1](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf),
[IPT067N20NM6](https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipt067n20nm6-datasheet-en.pdf),
[BSC016N06NS](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bsc016n06ns-datasheet-en.pdf),
[Vishay 86573](https://www.vishay.com/docs/86573/bzg03b-m-serie.pdf),
[Vishay 86574](https://www.vishay.com/docs/86574/bzg03c-m-series.pdf),
[Mersen clips](https://www.mersen.com/sites/default/files/medias/PIM/files/DS-Clips-for-Cylindrical-fuses-IEC-EN.pdf),
[Würth terminal drawing, reel variant](https://docs.rs-online.com/706f/0900766b815da3af.pdf).
The three PROFET source references are also recorded in `sense-screen.json`.

The retained ATOs are rated 32 VDC / 1 kA interruption; F9's interruption rating
and the unverified MRBF/ATO series coordination still limit claims about direct
battery faults. A 40 A MRBF is not a 40 A prospective-fault-current limiter.
Start on a current-limited bench source. Record the actual battery/fuse models,
fault coordination, thermal ramp, pump start/stop, loaded recovery and surge results
before installation release. These open hardware tests do not change passive BYPASS.
