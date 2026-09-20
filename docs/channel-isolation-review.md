# Revision C channel protection

Revision C implements the requested behavior: an output fault is handled by that
channel's hardware breaker, in both AUTO and BYPASS. Fabrication status is recorded
in [release-status.json](release-status.json); this document is not a release token.
The withdrawn revision-B Gerbers do not implement this circuit.

## Circuit and coordination

Battery → LM74800 reverse-polarity stage → TPS2492 common startup/backup stage →
shared bus. The logic supply uses this bus. Each channel then has its own TPS2492,
single shunt and LFPAK88 pass MOSFET, ahead of the three-clip fuse COM terminal.
AUTO passes through the PROFET; BYPASS goes directly from the fuse to the output.
Both positions retain the new hardware breaker. The fuse remains backup protection.

U21–U28 are **TPS2492PWR**, with Q11–Q18 **PSMN1R8-80SSEJ**. A fault latches only
its local controller. SW3–SW10 pull the corresponding UVEN low to reset that
channel. A persistent fault trips again after reset. MCU reset or stopped firmware
does not disable protection. Loss of input/enable can clear these volatile latches;
there is no nonvolatile fault memory and no timed automatic retry.

| Channels | Maximum fuse | Shunt | Current-limit screen | Startup load envelope |
|---|---:|---:|---:|---|
| 1, 2 | 10 A | 4 mΩ | 10.61–14.63 A | 10 A full-voltage resistor + 1000 µF actual |
| 3–7 | 5 A | 8 mΩ | 5.31–7.31 A | 5 A full-voltage resistor + 1000 µF actual |
| 8 | 20 A | 2 mΩ | 21.23–29.26 A | 10 A full-voltage resistor + 1000 µF actual |

CH8 retains its 20 A fuse ceiling and has a lower startup envelope. Electronic
constant-power loads and motors need individual bench checks; this resistor model
does not qualify every load drawing the same steady current. All channel currents
sum toward the **40 A continuous target**, which still requires thermal measurement.

The common R20 is 0.5 mΩ, giving an 87.80–112.82 A backup limit. Forty amperes of
healthy load plus the largest branch limit is below its minimum threshold. This
common limit is not a 40 A continuous thermal breaker. R17/R18 set approximately
432 W nominal common MOSFET power limiting; C18/C25/C28 total 36 nF C0G. The
maximum fault timer is below 10 ms and the calculated worst power is below the
single-device 10 ms SOA at a 60 °C mounting base, including graph reserve.

MAIN_PG_N drives Q6 to enable branches after the shared reservoir charges. The
inverter uses the controller's reference, independently of 3V3. Twenty-four
35SVPF120M capacitors provide 2880 µF nominal on the common bus. This reservoir,
the raised common limit and local gate discharge all matter during a live short;
current-threshold arithmetic alone does not establish isolation.

Each local TIMER has two 100 nF U2J capacitors, giving an 18.42–55.47 ms initially
discharged timeout screen. U2J temperature dependence is included. PROG divider
resistors are 0.1%, 25 ppm/°C; the calculations reserve 1% total resistance error.
Q31–Q38 FMMT720TA PNP devices boost gate discharge through 10 Ω, with 100 Ω between
the controller and pass-MOSFET gate. A local STPS41L60CG clamp handles output wiring
inductance. A separate 10 Ω/Schottky network protects each controller's OUT sense
pin from negative switching spikes. Output LEDs also have reverse clamps.

See [exact corner calculations](channel-isolation-calculations.json) and the
[transient sensitivity results](channel-isolation-transients.json). The latter
uses TI's controller model with latch selection and PSpice Boolean syntax preserved.
The ideal TIMER-clamp TABLE can also use an equivalent piecewise-linear
behavioral current source for ngspice compatibility. The implementation and
numerical options are recorded per case. The fixture includes three controllers (common, faulted and healthy), finite gate capacitance and
3 nF drain–source capacitance per MOSFET, a 5 mΩ +
1 µH source and a 10 mΩ + 100 nH short loop. It checks pre-existing and live faults,
loaded startup, bus voltage, healthy-controller state and pass-MOSFET stress.
The MOSFET is an approximate level-1 model with gate-charge sensitivity, not a
manufacturer transient model. This is design screening, not measured hardware.

An [additional six-case study](all-channels-transients.json) models all nine
controllers with 1,000 µF on every output, at 9.5 V and 16 V. It combines the
most sensitive common-controller corner with the strongest, slowest local
controllers. All-channel startup, a pre-existing CH8 short and a live CH8 short
pass. Startup/live loads total 40 A before the fault; the pre-existing-short
case places 40 A on the seven healthy outputs, with 2 A auxiliary in every case.
The lowest live-fault bus voltage is 9.251 V; the largest combined SOA utilization
is 0.728. PROG follows each controller's reference during power-up, as the real
divider does. Some numerical variants initialize the unpowered circuit with
uncharged capacitors (`uic`); this and solver/TIMER implementations are recorded.

SOA uses Nexperia's published curves with all common-stage current attributed to
one MOSFET, a 60 °C mounting-base limit and 10% graph reserve. Live-fault stress is
split into the first 10 µs, the next 90 µs and the limiting tail; respective 10 µs,
100 µs and 100 ms rectangular-envelope utilizations are added conservatively.
Low-VDS points are compared at the curve's higher-voltage current knee, avoiding
mistaking the hot RDS(on) edge for a cold-device thermal failure boundary.

The bus can dip briefly during a fault. Healthy-load acceptance requires measuring
that dip against the actual equipment's minimum voltage and hold-up, plus checking
3V3 and ESP32 reset. The simulated source impedance is an explicit fixture model;
it is not a guarantee for arbitrary battery cables or converter loads. The first
assembled board must pass [bring-up](bring-up.md) before a service rating is assigned.

## Layout and assembly

The board is 334 × 172 mm, four layers with 2 oz outer and inner copper. Twelve M3
holes add support beside the channel groups. Each has a 4 mm copper exclusion
radius; select hardware fitting that envelope. J4's mating edge is aligned to the
board edge. Its NPTH copper clearance is at least 0.2 mm and shield-pad annular
rings are enlarged for 2 oz fabrication. Q1/Q2 DGATE uses In2, with extra source
vias so the bottom source copper is no longer divided by the gate track.

CH1, CH2 and CH8 have eight in-pad thermal vias; the other PROFETs have at least
six. These vias connect to VS, not ground. Local pass-FET drain/source via fields
and broad branch pours carry power. No signal tracks may cut the In1 ground plane.
The shared shunt has a close F.Cu Kelvin pair. USB retains its dedicated In2 ground
reference and the selected 90 Ω differential geometry.

JLC's published component-PTH annular-ring requirement (0.254 mm for 2 oz) and its
via-diameter requirement are separate table entries. Via diameter is at least
0.20 mm larger than drill in this design, exceeding the published preferred
0.15 mm difference. Check the final CAM/DFM results against the actual order.
[Fabrication capabilities](https://jlcpcb.com/capabilities/Capab).

The Panasonic F12 recommended lands are 13.1 mm overall, 4.3 mm inner gap and
1.9 mm width; the selected 10 × 12.6 mm footprint matches them. FMMT720 pinout is
1 base, 2 emitter, 3 collector. See the
[Panasonic mounting specification](https://industrial.panasonic.com/cdbs/www-data/pdf/AAB8000/AAB8000COL10.pdf)
and [FMMT720 datasheet](https://www.diodes.com/assets/Datasheets/FMMT720.pdf).

## Monitoring and test points

IN1 moves from IO7 to IO15. IO5 measures IMON (nominal 24 mV/A with the new shunt),
and IO7 measures the shared bus through a 115 kΩ / 10 kΩ divider (0.08 V/V).
Both ADC paths have series resistance, filtering and Schottky clamps. MAIN_FLT_N
uses IO42; branch FLT1–FLT8 use IO16/17/18/35/36/37/39/40. Fault outputs have
3V3 pullups. Firmware must use this revised pin map.

TP1–TP16 expose GND, BATT_RAW, BATT_MID, HS_VCC, HS_SENSE, HS_TIMER, HGATE_MAIN,
+12V, VIN, +3V3, MAIN_IMON, MAIN_FLT_N, MAIN_PG_N, BR_ENABLE, ADC_IMON and ADC_BUS.
TP17–TP24 expose branch TIMER1–TIMER8. Ground-referenced instruments must never
short a high-side Kelvin or gate node to ground through their probe clips.

Primary circuit references: [TPS2492](https://www.ti.com/lit/gpn/tps2492),
[PSMN1R8-80SSE](https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf),
[WSLP shunts](https://www.vishay.com/docs/30122/wslp.pdf).
