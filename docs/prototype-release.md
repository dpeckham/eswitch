# Revision B prototype fabrication release — 2026-09-19

Release scope: **prototype PCB fabrication for three manual assemblies and
controlled bench validation**. Assemble and validate one before populating the other two.
The exact approved sources and verification hashes are recorded in
[release-status.json](release-status.json). This is not production qualification
or permission to install an untested board in service.

## Decisions and engineering basis

The owner confirmed that 40 A applies to continuous operation and accepted
startup latch-off at a lower load. The owner also confirmed actual Keystone 3557
clips and an ATO fuse fit both positions of the printed three-clip footprint,
and both Wuerth connector types fit their printed footprints. Physical fit is
closed on that evidence; manufactured-board inspection still follows delivery.

Keep R17/R18 at 8.25 kΩ/1 kΩ and C18 at 10 nF. Increasing startup power to force
the 40 A corner to start is unnecessary under the accepted requirement.

The **startup validation target** is 9.5–16 V with maximum actual total protected
bus/connected-load capacitance of 220 µF, including tolerance, and either:

- a resistive load drawing at most 20 A at full input voltage, plus an
  auxiliary-current allowance of at most 2 A throughout startup; or
- an active-load current profile bounded by 5 A throughout the rise.

These are alternative load models. Include the board's logic input current in
the 2 A auxiliary allowance or the 5 A aggregate bound, as applicable. Measure
that current; a 2 A logic fuse does not enforce a 2 A ceiling. Constant-power loads and motor
inrush require their own trajectories. AUTO/BYPASS placement does not change
these aggregate limits. TIMER must initially be at or below 1.04 V for the
successful-start screen; rapid brownout recovery with residual charge may latch
off. The 20 A target is not a precise trip threshold: some larger loads can start.

The ideal low-corner calculation takes at most 0.504 ms for the resistor-plus-auxiliary case
and 0.358 ms for the 5 A case at 16 V/220 µF. Both fit the conservative 0.755 ms
remaining timer budget from 1.04 V, including a 25% duration allowance. The
separate transient study addresses the gate-limited interval, during which the
fault timer is not necessarily charging.

Twelve 200 ms simulations use TI's TPS2492 controller model, perturbed controller
corners and deliberately approximate MOSFET models. They cover low/high power
corners, 20 A and 40 A resistors, a startup short, a 5 A active load and gate-drive
sensitivity. All selected lower-load cases start; startup shorts latch; the
low-power 40 A case latches and the high-power 40 A case starts.

The SOA comparison assigns **all pass current to one Q3/Q4 device**. Published
25 °C black solid SOA curves are derated to a mounting-base limit of 60 °C using
(175−60)/(175−25), then reduced a further 10% for graph-reading reserve. Cases
exceeding derated DC SOA use the 100 ms curve against the **whole event window**,
including earlier gate delay/preheating. Worst simulated utilization is 85.8%;
the longest such window is 57.76 ms. The sampled low-voltage region below 1 V
is excluded from this graph comparison; steady conduction requires separate
thermal/current-sharing measurements.

This is a sensitivity screen, not a guaranteed tolerance simulation: the
MOSFET models are not manufacturer models, their capacitances/transconductance
are assumed, and source/layout parasitics and live-short overshoot are absent.
The scope and limitations are preserved in [transient results](input-transient-calculations.json).
The [clamp review](input-clamp-review.md) defines the initial laboratory limits
and the additional evidence needed before high-energy testing.

Sources: [Nexperia PSMN1R8-80SSE Fig. 3](https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf),
[Nexperia AN50006 temperature derating](https://assets.nexperia.com/documents/application-note/AN50006.pdf),
[TI controller model](https://www.ti.com/lit/zip/slum134).

## Manufacturing readiness and remaining qualification

The routed schematic/PCB agree. Recorded CAD checks cover ERC, DRC, unrouted
nets, native parity, independent pin/value/MPN checks, fuse labeling, antenna
keepout and USB reference-plane sampling. CAM review covers all four copper
layers, masks/silkscreen, outline and separate 628 PTH/6 NPTH drills. Assembly
PDFs are 1:1 component-side views. The 55-MPN purchasing BOM gives quantities
for **one complete module**; the purchaser applies the desired build quantity.
September 19 displayed stock was sufficient for three builds and is not reserved.

Order 253 × 75 mm, four layers, JLCPCB **JLC041622-3313**, ENIG, 2 oz outer **and
inner**, 1.6 mm nominal / 1.59 mm selected stackup. Do not substitute the stackup.
Review the manufacturer's upload preview against the supplied dimensions/layers
and plating before checkout; that vendor-specific preview has not been seen.
Choose the fabricator's offered bare-board batch quantity covering at least
three boards. The component BOM remains per board regardless of bare-board
batch quantity or spares.

Production remains blocked until [bring-up and acceptance](bring-up.md) records
establish startup/fault/recovery behavior, clamp waveforms, USB/current/regulator
performance, 40 A thermal performance of both positive and return paths, and an
operating/load envelope. UVEN/UVLO brownouts reset the hardware fault latch; it is
not nonvolatile. Deferred installation details have not been invented or qualified.
