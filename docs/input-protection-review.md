# Input protection — open engineering review, 2026-09-16

**Not approved for fabrication. A replacement topology is selected and present in
the schematic, but its PCB migration and engineering verification are unfinished.**
See [resume handoff](pcb-resume-handoff.md). The historical analysis below explains
the rejected stage; it is not a description of the latest schematic.

## Selected implementation at the paused checkpoint

- LM74800 U12 drives only the Q1/Q2 reverse ideal-diode bank.
- R20: CSS4J-4026R-1L00F, 1 mΩ four-terminal shunt. Separate Kelvin sense traces.
- U14: TPS2492PWR, hardware power/current limiting and fault latch-off.
- Q3/Q4: PSMN1R8-80SSEJ, 80 V enhanced-SOA LFPAK88, separate 10 Ω gate resistors.
- R12/R13: 115 kΩ/10 kΩ, 0.1%, OV divider. R14/R15: 56.2 kΩ/10 kΩ, 0.1%, UV divider.
- R17/R18: 8.25 kΩ/1 kΩ, 1%, PROG divider; nominal power limit about 216 W.
- C18: 10 nF C0G, nominal fault timeout about 1.48 ms. These nominal values are
  **not** a completed worst-case protection or startup qualification.
- D3: SMCJ24CA input clamp; D6: SMCJ16A protected-bus clamp;
  D7: STPS41L60CG-TR freewheel clamp. Verify coordination, energy and overshoot.

TPS2492 fault latch resets on UVEN-low or internal UVLO, as well as deliberate
battery removal. A sufficiently deep input brownout therefore resets it; it is
not a nonvolatile latch. No timed automatic retry is designed in. Review this
distinction and loaded UV/OV recovery before release.

[TI TPS2492 datasheet](https://www.ti.com/lit/ds/symlink/tps2492.pdf),
[Nexperia PSMN1R8-80SSE datasheet](https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf),
[Bourns shunt drawing](https://bourns.com/docs/product-datasheets/css4j-4026.pdf),
[ST freewheel diode datasheet](https://www.st.com/resource/en/datasheet/stps41l60c.pdf).

## Required behavior

- 9.5–16 V input, 40 A simultaneous continuous design target (owner approved).
- Reverse-polarity blocking and overvoltage disconnection around 17 V.
- Upstream battery fuse; no onboard main fuse.
- Startup with a mixture of AUTO and BYPASS positions is required. Include
  recovery after undervoltage/overvoltage; do not assume all loads are off.
- Load models, total input capacitance and motor inrush are unspecified.
- On excessive startup current or an input overcurrent fault, latch the entire
  board off until battery power is cycled. This is the owner's confirmed choice;
  automatic retry and firmware-dependent protection are not acceptable.
- Preserve the separate USB-only bench supply; never require the battery for
  initial programming and never connect battery and USB together in this mode.

## Why the superseded stage was rejected

The superseded PCB's Q3/Q4 devices are BSC016N06NS, driven together from LM74800 HGATE
with a 10 nF gate-to-ground slew network. HGATE sources 39–75 µA. Both intrinsic
gate charge and the external capacitor affect the loaded transition. The relevant
MOSFET criterion is linear-mode safe operating area (SOA), not just on-resistance
or pulse drain-current rating. Check a single device carrying the startup stress;
threshold mismatch prevents assuming equal sharing between parallel switches.

[TI LM7480-Q1 datasheet](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf),
[Infineon BSC016N06NS datasheet](https://www.infineon.cn/assets/row/public/documents/24/49/infineon-bsc016n06ns-datasheet-en.pdf),
[Analog Devices explanation of parallel hot-swap FET startup stress](https://ez.analog.com/power/f/q-a/549834/ltc4368-or-other-and-mosfet-in-parallel).

Merely reducing C18 increases capacitive inrush. Merely increasing it extends the
time dissipating power with resistive or electronic BYPASS loads connected.
Neither is an independently justified fix. An upstream branch/battery fuse is
not a microsecond/millisecond MOSFET SOA limiter.

## Historical candidate investigation (superseded by selection above)

- **PSMN1R8-80SSEJ:** 80 V, enhanced-SOA LFPAK88, substantially larger land pattern
  than the current PG-TDSON-8. DigiKey product page showed 1,884 available on
  2026-09-16. Requires a new symbol/pin mapping (gate 1, sources 2–4, drain mounting
  base), footprint and copper. Must still check gate-charge tolerances, case
  temperature and loaded startup; the SOA designation is not a blanket approval.
  [Manufacturer datasheet](https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf),
  [DigiKey](https://www.digikey.com/en/products/detail/nexperia-usa-inc/PSMN1R8-80SSEJ/27351652).
- **TI CSD18540Q5B/BT:** not selected because the reviewed DigiKey pages showed
  no stock. Do not add to the BOM without a new availability check.
- **LM74502H:** faster gate drive, but no reverse-current blocking and its
  datasheet expressly excludes the low-drive part's simple inrush circuit.
  Faster switching alone does not bound capacitive inrush. Not a drop-in cure.
  [TI datasheet](https://www.ti.com/lit/ds/symlink/lm74502-q1.pdf).
- **Current-limited hot-swap controller:** under consideration so an excessive
  startup load can disconnect without destroying the pass devices. Requires
  sense-resistor sizing, fault timeout/foldback analysis, a suitable SOA FET,
  and hardware latch-off (owner-confirmed). This is an additional
  protection function, not a replacement for the upstream battery fuse.

## Required before release

1. Set an explicit startup load/capacitance envelope and safe overload behavior.
2. Calculate worst-case current, voltage and duration against derated single-FET
   SOA, including component tolerance and hot restart; verify current-sharing
   assumptions separately for steady conduction.
3. Check reverse connection, OV/UV transitions, source/cable inductance, secondary
   TVS coordination and stored energy in external loads.
4. Implement and verify schematic, footprints, layout, Kelvin sensing where used,
   BOM stock, ERC, DRC and schematic/PCB parity.
5. Specify prototype tests: mixed-position cold and hot startup, load steps,
   brownout/OV recovery, fault disconnection and thermal rise. These physical
   tests occur after prototype fabrication; they have not been performed.
