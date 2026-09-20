# Revision C power review — 2026-09-19

The current circuit, coordination limits and model assumptions are documented in
[channel protection](channel-isolation-review.md). The source-bound CAD and
fabrication decision is in [release-status.json](release-status.json). Revision-B
input-stage calculations and startup explanations are historical; their 1 mΩ
shunt and 10 nF timer do not describe revision C.

## Current protection and thermal scope

Each AUTO/BYPASS channel has a TPS2492 hardware breaker upstream of its fuse.
The common startup/backup stage uses a 0.5 mΩ shunt, 36 nF C0G timer and the
existing approximately 432 W nominal power setting. Its 87.80–112.82 A current
limit leaves room for a local branch to clear a fault while healthy channels
remain supplied. It does not enforce the 40 A continuous thermal target.

The channel calculations include shunt and precision-divider error, timer
current/threshold/capacitance corners, startup charge and derated single-FET SOA.
The transient study additionally includes the shared 2880 µF reservoir, its ESR,
source and fault-loop inductance, gate-discharge boosters and a healthy controller.
See [calculations](channel-isolation-calculations.json),
[transient evidence](channel-isolation-transients.json) and their reproducible tools.

The 334 × 172 mm, four-layer board uses 2 oz outer and inner copper. Explicit
power pours and via arrays carry branch current; the PROFET thermal vias connect
to VS. The input reverse-FET gate route no longer divides the bottom source pour.
In1 remains a ground reference. Thermal-via count and copper dimensions are
geometric evidence, not measured temperatures or an installation current rating.

Forty amperes aggregate continuous operation, 20 A CH8 operation, actual load
startup and healthy-equipment ride-through still require the instrumented tests
in [bring-up.md](bring-up.md). The model's 60 °C MOSFET mounting-base ceiling must
be confirmed in the intended cooling arrangement. Build one assembly first.

## Buck capacitance and USB

The output-capacitor selection is corrected. C7/C8/C12/C13 now use
**GCM32ER70J476KE19L, 47 µF/6.3 V X7R ±10%, 1210**. The footprint and copper
are unchanged. Four parts provide 188 µF nominal on the **3.3 V rail only**.
Do not use these 6.3 V parts on VIN or battery nets.

`python3 tools/buck_analysis.py --check` checks the exact selected model, part
assignments and saved calculations. Murata SimSurfing's combined temperature,
DC-bias and 10 mVrms AC model was sampled from −55 to 125 °C in 5 °C steps and
0–3.7 V in steps below 0.04 V. The lowest sample is 20.503 µF per part. Applying
10% initial tolerance and a further 20% engineering reserve gives
**4 × 20.503 × 0.90 × 0.80 = 59.05 µF**, 47.6% above TI's 40 µF requirement.
Temperature and bias are already included in the model; they are not deducted
twice. The extra reserve is a design allowance for unmodelled variation/ageing,
not a manufacturer-guaranteed tolerance. Sampled typical data do not establish
a guaranteed continuous minimum.

The exact-model evidence gap is closed for engineering screening. Production
acceptance still requires fitted-capacitor/rail validation, stability and startup
measurements. The larger bank changes startup charge; repeat USB input-current
measurements with the selected parts. The calculation does not certify USB
current-budget compliance. See [saved calculation](buck-capacitance-calculations.json)
and [manufacturer model samples](evidence/buck-capacitance-murata.json).

The superseded GRM32ER71A226KE20L selection had no exact K-tolerance model in the
retrieved catalog. Its related M-tolerance model was not used as substitute proof.
The new exact part is listed active and the 2026-09-19 DigiKey page audit showed
106,406 available against 12 required. Inventory observations may be cached and
must be reconfirmed at checkout.

The saved B.Cu USB data traces use 0.235 mm width. The geometry check samples their
centres and both copper edges every 0.1 mm against filled In2 GND and passes
3,276 positions. Pair path lengths before the series resistors are approximately
48.54 and 52.18 mm; MCU-side segments are 2.23 mm each. The 3.64 mm mismatch and
connector breakouts still require functional USB review; the sample check is
not an impedance field solver or USB certification. The exact selected stackup
is recorded separately. Bench startup/current-budget testing remains open.

Sources: [TI TPSM63603 datasheet, Table 7-1](https://www.ti.com/lit/ds/symlink/tpsm63603.pdf),
[Murata capacitance-bias guidance](https://www.murata.com/en-us/support/faqs/capacitor/ceramiccapacitor/char/0005),
[Murata SimSurfing](https://ds.murata.com/simsurfing/mlcc.html),
[JLCPCB four-layer 2 oz trace/space capability](https://jlcpcb.com/pcb-fabrication/fr4-pcb).
