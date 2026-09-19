# What the 16 V / 40 A startup stall means

This is a **prediction from a tolerance-screening model**, not a measured board
failure. The owner resolved this requirement by accepting lower-load startup
latch-off; see the [prototype release](prototype-release.md).
The saved circuit still uses R17 = 8.25 kΩ, R18 = 1 kΩ and C18 = 10 nF.

## How the stall happens

The input pass MOSFETs act as a controlled resistance while the output rises.
They must carry the connected BYPASS loads as well as charge the bus and load
capacitors. During this interval they can dissipate far more power than when
fully on. TPS2492 deliberately restricts that dissipation.

For the illustrative 40 A resistive load at 16 V, R = 16/40 = 0.4 Ω.
At an intermediate output voltage V, load current is V/0.4 and the MOSFETs
drop 16 − V volts. Their required power, before capacitor charging, is therefore
**P = V × (16 − V) / 0.4**. It peaks at **160 W**, at 8 V output and 20 A.
That is heat in the pass stage during startup, not the load's 640 W running power.

The nominal programmed limit is 216.2 W, but the low tolerance screen is
137.9 W. At this setting the rising output reaches an equilibrium near
**5.03 V and 12.57 A**: all available current supplies the resistor and none
remains to raise the output. The later mathematical root at 10.97 V does not
provide a path through the intervening power deficit. Extending the timeout
alone cannot solve this. Once limiting persists, the controller latches off;
actual gate dynamics and timing can interrupt the rise before that equilibrium.

The 137.9 W calculation includes REF voltage, divider/shunt tolerances, PROG
bias and the power engine's ±32% screen. TI's support clarification explicitly
uses ±32%; the electrical table establishes limits at specific test points.
This remains an engineering screen at our PROG setting, not a separately
guaranteed complete circuit model. The 44.55–55.56 A current-limit range is a
different constraint: it does not remove power limiting during startup.

Sources: [TPS2492 datasheet](https://www.ti.com/lit/gpn/TPS2492),
[TI power-limit accuracy clarification](https://e2e.ti.com/support/power-management-group/power-management/f/power-management-forum/1074250/tps2492-how-precise-is-the-constant-power-engine-what-measurement-method-will-best-match-the-designed-power-limit).

## Concrete setting comparisons — none selected or approved

These comparisons use the same **illustrative** 16 V, 0.4 Ω load and 1,000 µF
total bus/load capacitance. The capacitance is not an owner-supplied load
specification. Each candidate changes only two fitted values in the existing
footprints, but electrical approval is still required.

| R17 / C18 | Low power screen | Ideal charge time | Minimum timer | High power × maximum timer |
|---|---:|---:|---:|---:|
| 8.25 kΩ / 10 nF, currently fitted | 137.9 W | Stalls | 1.029 ms | 0.769 J |
| 6.81 kΩ / 100 nF | 163.7 W | 7.784 ms | 10.292 ms | 9.093 J |
| 6.19 kΩ / 47 nF | 178.0 W | 3.341 ms | 4.837 ms | 4.638 J |
| 5.62 kΩ / 33 nF | 193.6 W | 2.382 ms | 3.396 ms | 3.533 J |
| 5.11 kΩ / 27 nF | 209.9 W | 1.926 ms | 2.779 ms | 3.129 J |

The smallest power increase has little margin over 160 W and needs the longest
timeout. A larger increase can reduce total limited fault energy, while raising
peak stress. **The final column is not a total fault-energy bound**: TIMER runs
while limiting, and gate-limited intervals and switching overshoot are omitted.
None of these rows proves single-device hot SOA, fast-short survival or startup
with an arbitrary electronic load. Parallel sharing is not credited.

Real electronics can draw almost constant power above their undervoltage
threshold; motors can draw starting or stalled current. Neither is equivalent
to the resistor example. Those loads and their capacitance need a bounded
startup envelope and prototype validation.

## Owner decision — 2026-09-19

The owner accepted startup latch-off at a lower load while keeping the 40 A
continuous target. Successful full-40-A BYPASS startup is not required. The selected validation target is a 20 A resistor plus a 2 A auxiliary-current
allowance, or a 5 A total active-current bound, with at most 220 µF actual
bus/load capacitance. Analytical and transient sensitivity checks now support
controlled prototype fabrication. Hardware startup/fault tests remain required.

Run `python3 tools/input_stage_analysis.py --check` to check the saved numerical
evidence, or add `--plot` to export the explanatory PNG/PDF under `out/review/`.
The integrator is cross-checked against independent unloaded and resistive-load
closed forms. CAD verification now checks calculation freshness too; a passing
freshness check is not a hardware test. See `tools/input_stage_transient.py`
for the separate gate-dynamics sensitivity study.
