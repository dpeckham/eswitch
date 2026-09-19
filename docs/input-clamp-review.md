# Input clamp review — prototype scope, 2026-09-19

The fitted clamps provide a plausible prototype protection network. Their
datasheet pulse ratings do **not** qualify an unspecified battery feeder, an
energized short circuit, or arbitrary inductive loads. This review permits
controlled prototype evaluation; installation transient qualification remains
a production gate.

## Coordination

| Device | Published point at 25 °C | Review consequence |
|---|---|---|
| D3, Littelfuse SMCJ24CA, raw input | 24 V stand-off; 26.7–29.5 V breakdown; 38.9 V clamp at 38.6 A | Below the 50 V input capacitor and 60 V reverse-FET ratings at this test point. The 55.56 A controller current-limit corner exceeds that specified clamp current: 38.9 V is not a bound for that event. |
| D6, Littelfuse SMCJ16A, protected bus | 16 V stand-off; 17.8–19.7 V breakdown; 26 V clamp at 57.7 A | Nominal coordination with the 28 V PROFET supply ceiling has only 2 V headroom. Temperature, pulse shape and trace inductance must be measured. |
| D7, STPS41L60CG-TR, GND to protected bus | Per diode: 0.60 V maximum at 20 A, 0.77 V at 40 A, at 25 °C under the stated pulse conditions | At 40 A, only 0.23 V remains before the TPS2492 OUT pin's −1 V absolute minimum. Attribute the entire current to one diode; tied anodes do not prove sharing. |

The TVS 1500 W rating uses a 10/1000 µs waveform, specified mounting copper,
and temperature derating. It is neither continuous power nor a universal joule
rating. The published 0.1%/K breakdown coefficient is typical; it cannot establish
a guaranteed hot clamp voltage. D6's forward conduction also cannot replace D7
as a sub-1 V negative clamp.

Sources: [Littelfuse SMCJ datasheet, February 2025](https://www.littelfuse.com/assetdocs/littelfuse_tvs_diode_smcj_datasheet.pdf?assetguid=37388813-0d6d-4329-969b-1aa8b7614ac1),
[ST STPS41L60C datasheet](https://www.st.com/resource/en/datasheet/stps41l60c.pdf),
[TI TPS2492 datasheet](https://www.ti.com/lit/gpn/TPS2492).

## Energy and test-fixture limits

For feeder inductance L and interrupted current I, initial stored energy is
L I²/2. If a source at Vs keeps feeding a clamp at Vc during decay, the ideal
clamp energy is L I²/2 × Vc/(Vc−Vs). Include this source contribution; using
only stored energy underestimates the input TVS burden.

For illustration, L = 10 µH, I = 5 A, Vs = 16 V and Vc = 38.9 V give 0.125 mJ
stored, approximately 0.212 mJ in D3, 194.5 W initial clamp power and 2.18 µs
ideal decay. These are fixture calculations, **not measured wiring or a clamp
guarantee**. A 40 A feeder stores 64 times as much energy at the same inductance;
it also exceeds D3's specified clamp-current point. Source output capacitors,
load capacitors, contact bounce and parasitic overshoot are absent from this
calculation. A bench supply's current-limit setting alone does not bound its
output-capacitor discharge current.

For the first powered checks, use a protected, current-limited laboratory source,
short paired leads, no external inductive loads and no deliberate energized
short. Begin with no branch fuses and a limit at or below 1 A; increase to at most
5 A only as needed after inspecting the rails. Document the fixture's output
capacitance, inductance and protection before fault testing. Deliberate transient
tests need an independently energy-limited fixture and a pulse-specific review.

Use differential probes at component pins, including U14 OUT relative to its
local GND. Initial measurement acceptance targets are raw input below 45 V,
protected bus below 27 V and OUT above −0.8 V; these are conservative test goals,
not additional component ratings. A scope limit is an acceptance check, not
instantaneous protective action. Stop increasing stress after any failed goal.
Keep Q3/Q4 mounting bases at or below 60 °C for the saved SOA screen; this is
not a 60 °C ambient rating. Verify the temperature measurement accounts for the
hidden mounting base rather than assuming the package top has the same temperature.

Increase startup, interruption and load-step currents in stages after recording
waveforms. Before any energized high-current short, review measured loop
inductance, source discharge current, controller response, individual gate
discharge and transient SOA. Before attaching motors/relays, review their stored
energy and local flyback/suppression. Reverse-polarity tests also start with a
limited source; the forward-path startup model does not test LM74800 behavior.

## Disposition

No clamp-value change is justified by the bounded initial bench work. The
voltage-coordination review is complete for prototype ordering. Full-current
fast-short survival, hot bus clamping, negative OUT overshoot, repetitive pulses
and installation fuse/cable/load coordination remain unqualified. These are
explicit limits of the prototype release, not findings erased by a CAD pass.
