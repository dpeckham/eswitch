# Eight-channel redesign — routed prototype

Start with [`eswitch-simple.kicad_pro`](eswitch-simple.kicad_pro).
The completed **136 × 104 mm, four-layer PCB** is
[`eswitch-simple.kicad_pcb`](eswitch-simple.kicad_pcb). Native KiCad 10 reports
**zero DRC violations, zero unconnected nets and zero schematic-parity findings**.
See [build notes](BUILD.md) for dimensions, stackup, assembly and qualification status.

Current exports are in `../fab/`: `eswitch-simple-project.zip`,
`eswitch-simple-fabrication.zip`, `board-top.png` and `board-bottom.png`.
The electrical/thermal bench qualification described below remains open.

The compact layout places four channels on each of two opposite output edges.
It is **31.1% smaller in PCB area** and **40.4% shorter in its longest dimension**
than the earlier 228 × 90 mm layout, retaining the same components and eight mounts.
Old releases and backups have been removed from this worktree.
`compact-copper-review.json` compares the filled VS heat-spreader areas and raw
spine widths. The reduced heat-spreader area needs thermal validation at the
retained 40 A aggregate target; PCB size does not include cable/enclosure clearance.

## Agreed architecture

Eight ESP32-controlled PROFET high-side switches, with one ATO blade fuse and
three individual clips per channel. The middle clip connects directly to the
raw battery distribution bus. A fuse connects it either to the PROFET supply
(AUTO) or to the load (BYPASS). Removing the fuse is OFF. Battery power is
disconnected before moving fuses. Fuse maxima are 10/10/5/5/5/5/5/20 A;
40 A simultaneous operation is the design target, not an established rating.

```
AUTO:    BATT_RAW -- fuse -- VS -- PROFET -- LOAD
BYPASS:  BATT_RAW -- fuse ------------------ LOAD
                                  PROFET OUT remains connected
```

During recovery, ALL usable channels may be put in BYPASS; faulty/unused channels
may have their fuses removed. Automatic operation and uninterrupted healthy-load
ride-through during the fault are not requirements of this redesign. A destructive
short can require abandoning the affected channel. Common copper/terminal damage
and an externally backpowered load are outside this fuse-only recovery promise.

The logic converter has its own F9 fuse. Neither branch mode depends on a shared
electronic input switch. Branch VS nets are separate; no reservoir, clamp, supply,
or copper connection is allowed to join them together. The bypass path contains
no diode, relay, MOSFET, electronic breaker, or detachable jumper in series.

## First-pass component decisions

- Retain BTS7004-1EPP on CH1/2, BTS7008-1EPR on CH3–7, BTS7002-1EPP on CH8.
  These eight ICs cost about $14.54 per board at the recorded three-board prices.
  They integrate switching, current diagnosis, and overload/temperature latch-off.
- Remove the nine TPS2492 controllers, ten enhanced-SOA pass FETs, branch shunts,
  24-capacitor shared reservoir, gate boosters, and separate latch-reset buttons.
- Give each channel independent IN and DEN signals, with local pull-downs on both.
  A shared DEN pulse could reset an OFF channel's internal fault latch. Firmware
  must respect the native latch-reset timing and must not automatically retry faults.
- Keep eight ADC1 current-sense inputs and output LEDs. Current measurement is
  valid for AUTO, not BYPASS. Backpowered VS cannot reliably identify fuse position;
  firmware must not infer AUTO from VS voltage or pretend to measure bypass current.
- Retain ESP32-S3, USB-C programming, boot/reset, UART, Wi-Fi/BLE and OTA capability.
  Firmware is not implemented in this repository. Initial USB use remains
  battery-disconnected. The new pin map is in `pin-map.json`.
- Retain the previously researched TPSM63603 converter and USB ideal-diode circuit
  for the first draft. This is a deliberate reuse of a functional subcircuit,
  not an assertion that these are the cheapest possible logic-supply components.
- Use individually fused local VS TVS candidates rather than an unfused suppressor
  across the raw shared bus. Suppressor sizing/coordination is still open.
- Keep direct-entry output blocks and M5 input terminals. The board uses
  eight mounting holes and the heavy-copper four-layer stackup.
- Route the ADC clamp diodes to an independent 2.495 V TLA431 shunt reference,
  biased through 2.2 kΩ, rather than dumping fault current directly into 3V3.
  `electrical-screen.json` records the DC assumptions; power-down and dynamic
  behavior still require measurement.

## Inverse current: allow it, bound it

All three selected PROFET datasheets, section 7.3.1 (pp. 23–24), describe inverse
current. With OUT above VS, an OFF device conducts through its body diode; an ON
device can conduct through its channel. Overload/overtemperature protection is
not active for inverse current. The stated InverseON capability is not an OFF-state
body-diode continuous-current rating or a qualification of output-powered startup.

In BYPASS, normal load current flows directly through the fuse. Only local VS
capacitance and local electronics are fed backward. Each channel presently has
100 nF VS-to-board-ground and 47 nF VS-to-device-ground, not a shared millifarad
reservoir. Bounds on the startup charging pulse still need evaluation.

The new local DEN pull-down is important. The BTS7008 datasheet specifies at most
0.5 uA disabled IS leakage under its stated conditions (section 9.5), versus up to
3.5 mA open-load/OFF diagnostic current and 10 mA fault-report current. Simply
leaving DEN active with a dead ESP32 could therefore feed the logic rail through
the ADC clamps. Healthy unpowered-control behavior must be checked through the
entire ramp/brownout, not inferred just from the 0 V endpoint. The GPIO pull-downs
do not protect against arbitrary internal chip damage.

## Electrical work still required

1. **Healthy bypass:** measure/bound OUT-to-VS charging, local inverse current,
   DEN/IN levels, IS voltage and 3V3 injection for all-bypass and mixed modes;
   controller running, held reset, power absent, and logic rail shorted.
2. **Input protection:** raw BYPASS deliberately has no electronic reverse-polarity
   or overvoltage disconnection. This first AUTO draft also does NOT reproduce
    revision C's reverse-blocking stage or approximately 17 V disconnect. The
    agreed scope is correctly connected 9.5–16 V operation; native PROFET reverse-battery
   robustness is not reverse-voltage protection for connected loads.
3. **Transients/inductance:** verify local SMCJ16A clamp voltage AND energy,
   connection inductance, switch avalanche limits, negative output stress, and
   reverse-biased LED protection. No installation surge envelope has been supplied.
4. **Fault recovery:** confirm a removed branch fuse stops battery-fed power into
   a grounded faulty branch, and assess signal-interface coupling to other
   channels. A damaged shared bus or arbitrary GPIO short is not covered by a
   simple power-net connectivity model.
5. **Load/thermal:** check fuse/contact derating, 40 A common copper, 20 A branch
   heating, native PROFET trip thresholds, load inrush, and inductive turn-off.
   Fuse maxima do not specify guaranteed continuous load currents.
6. **Logic/USB:** converter layout/stability, current budget, reset behavior,
   power-down injection, and USB headroom/startup on the new layout.

## Cost and reproducibility

The priced draft component subtotal is **$104.04 for one board**, or **$92.76 per
board** when buying exactly three sets together, **excluding the unpriced
TLA431AIDBZR**. These are historical-price
estimates of the present draft, not final build prices. The previous design's
three-board component/fuse subtotal excluding standoffs was approximately
$261.64 per board. The reduction follows the newly agreed recovery requirements;
it is not a claim of equivalent revision-C protection behavior.

`bom-draft.csv` contains per-board fitted quantities (including individual clips
and eight fuse inserts). `cost-estimate.json` applies the **2026-09-19 historical
price observations** to these new quantities. It is a component subtotal, not an
order quote. Eight standoffs are included; PCB fabrication, assembly, additional
installation hardware and unpriced parts are excluded. Current stock and prices
have not been refreshed.

```
python3 redesign/generate.py
python3 redesign/verify.py
python3 redesign/analysis.py
```

`just schematic` runs both commands. Native KiCad on macOS is discovered directly;
set `KICAD_CLI` elsewhere if needed. Review exports and a source-hashed check summary
are written to `out/redesign/`, including `eswitch-simple.pdf` and `erc.json`.

Generation uses shared symbol/footprint assets and drawing utilities, but never
calls the revision-C circuit builder. Verification compares exported KiCad
connectivity and checks the passive power-path mode/fault model. These checks
do not establish transient, thermal, reverse-current or installation qualification.

`compact.py` and `route_checked.py` require KiCad's Python (`pcbnew` and `wx`). Copper
filling runs through `native.py` using the native KiCad CLI, because the Python
zone-filling API crashes in this environment. The transactional router retains
only batches passing native copper DRC; its intermediate boards can still have
unconnected nets. A clean placement DRC is not a completed routing check.
`compact.py` generates a compact placement candidate; it does not replace the
finished PCB. Subsequent routing and local corrections are retained in the
authoritative PCB. Obsolete layout generators and intermediate boards were removed.
`python3 redesign/export.py` rechecks final PCB parity/DRC and recreates both ZIPs.

### Manufacturer references

- [BTS7008-1EPR, rev 1.00, 2024-10-01](https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7008-1epr-datasheet-en.pdf)
- [BTS7004-1EPP, rev 1.11, 2024-07-29](https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7004-1epp-datasheet-en.pdf)
- [BTS7002-1EPP, rev 1.11, 2024-07-29](https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7002-1epp-datasheet-en.pdf)

Use section 7.3.1 for inverse current, 8.3 for intelligent latch behavior, 9 for
diagnosis, and 10 for the application interface. Retrieved 2026-10-25.
