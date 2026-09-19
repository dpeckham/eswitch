# Revision B power review — 2026-09-19

**Prototype design screening complete within the bounded bench scope.** See
[prototype release](prototype-release.md) for the release limits and
[clamp review](input-clamp-review.md) for transient limitations. Production
qualification requires the physical tests in [bring-up.md](bring-up.md).

## Input-stage result

The fitted settings are unchanged: R17/R18 = 8.25 kΩ/1 kΩ and C18 = 10 nF.
Reproducible component/controller corner calculations give:

- Current limit: 44.55–55.56 A; the 40 A shunt dissipates 1.584–1.616 W.
- UV rising: 8.60–9.27 V; OV rising: 16.23–17.52 V.
- Timer, initially discharged: 1.029–2.532 ms.
- Power-limit screen: 137.93–303.80 W. TI's published test-point accuracy is
  extrapolated to this PROG setting; this is not a guaranteed complete-circuit
  tolerance specification.

At 16 V, a 40 A resistor requires 160 W peak pass-stage power while starting.
The low power corner stalls; the owner explicitly accepted lower-load startup
latch-off while retaining the 40 A continuous target. The
[startup explanation](input-startup-explained.md) derives the 5.03 V equilibrium.

The selected prototype validation envelope uses at most **220 µF actual total
bus/load capacitance**, either a 20 A-at-full-voltage resistor plus up to 2 A
auxiliary current throughout startup, or a 5 A total active-current bound.
The auxiliary allowance includes the board's logic supply; its actual input
current still needs measurement. A 2 A logic fuse does not guarantee that bound.
These are alternative envelopes. Initial TIMER must be at or below 1.04 V;
rapid brownout recovery may latch off. See `input-stage-calculations.json` for
all six input-voltage/load cases and margin against the 0.755 ms timer budget.

Twelve transient sensitivity cases use TI's controller model and approximate
MOSFETs, varied gate drive and deliberately enlarged capacitance. All lower-load
cases start and startup shorts latch. Total startup may greatly exceed TIMER's
nominal duration because the timer charges only while limiting. Single-FET SOA
is checked with all pass current attributed to one device, at a mounting-base
limit of 60 °C and an additional 10% graph reserve. Complete fault-event windows
are checked against the 100 ms curve; the saved results are in
[input-transient-calculations.json](input-transient-calculations.json).

The black solid 25 °C curves from the exact Nexperia datasheet are used. No hot
rating is inferred from unlabeled red curves. The model omits source/layout
parasitics, real MOSFET nonlinear capacitance/temperature effects and energized
short-circuit overshoot. Its on-resistance does not establish steady thermal
performance. This is sufficient evidence to build controlled bench prototypes;
it is not a guaranteed startup rating or fast-short qualification.

Sources: [TI TPS2492 datasheet](https://www.ti.com/lit/gpn/TPS2492),
[TI transient model](https://www.ti.com/lit/zip/slum134),
[Nexperia PSMN1R8-80SSE datasheet](https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf),
[Nexperia AN50006](https://assets.nexperia.com/documents/application-note/AN50006.pdf).

## Copper and thermal observations

The input positive path uses F.Cu/In2.Cu/B.Cu pours and via arrays around the
reverse FETs, Kelvin shunt and pass FETs. The downstream common positive bus is
primarily F.Cu/In2.Cu. In1 remains GND with no foreign signal tracks. Channel 8
has its additional In2 supply/output copper; each PROFET exposed pad connects to
VS spreading copper, not ground.

A sampled vertical section of the candidate's filled In1 GND pour at x =
49, 55, 65, 75, 85, 100, 120, 130, 160, 190, 220 and 240 mm found between 59.7
and 74.1 mm total GND width. Other ground layers add parallel copper. This is
geometric evidence only: disconnected branches, current crowding, terminal
fields, minimum necks and via plating prevent turning summed widths into a
qualified resistance or 40 A rating. No current-density/thermal solver result or
measured temperature rise is available. The positive and return paths both need
the instrumented voltage-drop/thermal tests in [bring-up.md](bring-up.md).

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
3,153 positions. Pair path lengths before the series resistors are approximately
47.22 and 49.53 mm; MCU-side segments are 2.23 mm each. The 2.31 mm mismatch and
connector breakouts still require functional USB review; the sample check is
not an impedance field solver or USB certification. The exact selected stackup
is recorded separately. Bench startup/current-budget testing remains open.

Sources: [TI TPSM63603 datasheet, Table 7-1](https://www.ti.com/lit/ds/symlink/tpsm63603.pdf),
[Murata capacitance-bias guidance](https://www.murata.com/en-us/support/faqs/capacitor/ceramiccapacitor/char/0005),
[Murata SimSurfing](https://ds.murata.com/simsurfing/mlcc.html),
[JLCPCB four-layer 2 oz trace/space capability](https://jlcpcb.com/pcb-fabrication/fr4-pcb).
