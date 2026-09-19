# Revision B validation and production acceptance

Status: **not performed**. These tests require assembled hardware, instruments
and a defined test fixture. Passing the saved-board CAD checks does not satisfy
them. Start with one assembled board; use the other two after the first passes.
The test record must identify PCB/schematic hashes, fitted MPNs, firmware version,
fixture protection, wiring, load models, ambient and measured waveforms.

## Prototype release and initial limits

[Prototype release](prototype-release.md) records the completed design screen,
physical-fit confirmation and CAD/CAM basis for ordering. The startup validation
target is 9.5–16 V, at most 220 µF actual total bus/load capacitance and either a
20 A full-voltage resistor plus at most 2 A auxiliary current, or a 5 A aggregate
active-current bound. Include the board's logic demand; measure it, since a fuse
value does not guarantee a current ceiling. Initial TIMER must be at or below
1.04 V for the success screen. Larger loads may start or latch; 20 A is not a
precise trip threshold. Full-40-A startup is not required.

Follow the [clamp review's staged laboratory procedure](input-clamp-review.md).
Initially use a protected bench source, no external inductive loads and no live
short. Begin without branch fuses, at or below 1 A current limit, then at most
5 A as needed after rail checks. Account for the supply's output-capacitor
energy; current limiting alone does not bound a fault pulse.

Measure raw input below 45 V, protected bus below 27 V and local TPS2492 OUT
above −0.8 V. These are acceptance goals, not protection circuits. Keep Q3/Q4
mounting bases at or below 60 °C for the saved SOA screen; package-top or ambient
temperature alone does not prove this. Advance to larger startup, steady-load and
fault tests only after recording the preceding waveforms and bounding fixture
energy. Review a high-current energized-short fixture before using it.

## Assembly inspection and logic

1. Check the 253 x 75 mm outline, finished holes and all connector/fuse footprints
   against real parts and the 1:1 drawings. Confirm one fuse per three-clip cell;
   J1/J6–J12 pin 1 is GND and pin 2 is LOAD+. Check all nine pins of each input
   terminal and support the ESP32 overhang.
2. Inspect solder joints and polarity before power. U1–U8 thermal pads are VS;
   U9 PGND/output pads follow its separate land pattern. Q3/Q4 mounting bases
   are drains. Do not infer continuity from a 3D picture.
3. Use a current-limited bench supply and external fixture protection. Start
   without branch fuses or external loads. Measure VIN and 3V3; confirm reset,
   BOOT and UART access. Check every input and output remains OFF during reset,
   firmware boot, watchdog reset and brownout.
4. Disconnect the battery connector completely for USB tests. At the board's
   USB connector, test VBUS at 4.0, 4.4, 4.75 and 5.25 V. The 4.0 V case is a
   margin exploration, not a promised minimum host voltage. Measure startup,
   flash/program/reset cycles, USB enumeration, ripple and peak/average input
   current. Repeat with a representative long cable and powered hub. Verify
   host current-budget compliance before enumeration and after configuration;
   successful enumeration alone does not prove compliance.
5. Check the 3V3 rail remains inside the ESP32/module limits through boot and RF
   load steps, with no oscillation, dropout or unwanted branch activation. Log
   output-capacitance conditions and temperature. Check RF performance with the
   final mechanical surroundings; no copper under the antenna is only a layout
   prerequisite.

## Input protection and loaded startup

Probe source voltage, shunt differential voltage, bus voltage, TIMER and each
pass FET's VGS/VDS. Record current and temperature per device; do not assume equal
linear-mode sharing. Validate probe common-mode range and bandwidth first.

| Test | Conditions | Acceptance |
|---|---|---|
| Static thresholds | Sweep UV/OV slowly in both directions | Thresholds and hysteresis inside the completed tolerance analysis; no chatter |
| Mixed AUTO/BYPASS startup | 9.5, 12 and 16 V; cold and hot; resistor and representative electronic loads; sweep capacitance | Starts within the declared envelope; outside it, either starts within component limits or safely latches on a sustained limiting fault |
| Timer/fault behavior | Startup overload, overload after steady operation, repeated short load pulses | Fault timing matches the corner analysis; no unintended timed retry; cumulative timer behavior understood |
| Fast short | Protected laboratory short fixture, including hot steady operation | Peak current, VDS, VGS, bus undershoot and clamp stress remain within the reviewed limits |
| Reset/recovery | Input interruption, shallow/deep brownout and OV recovery with loads attached | Explicitly characterize UVEN/UVLO latch reset; no claim of nonvolatile latch-off |
| Reverse polarity | Current-limited source, progressing only within the approved test envelope | Blocking works in AUTO and BYPASS; leakage and component stress within their limits |
| Transients | Defined source/load inductance and stored energy | Peak voltage, pulse power and accumulated energy meet the approved clamp/SOA analysis |

Do not increase R17 power limit or C18 timeout merely to obtain a successful
startup: both changes require repeating the single-FET SOA and fault analysis.
Do not move fuses with battery power connected.

## Load, thermal and branch protection

Test the complete positive **and return** paths. Record four-wire voltage drops
across input terminals, Q1/Q2, R20, Q3/Q4, common bus, each active fuse/holder,
PROFET, output terminal and return path. Instrument source/drain via banks,
shunt terminals, the ground terminal and CH8 spreading copper.

Increase total load in controlled steps to 40 A with distributions that maximize
input-stage heating and far-end bus/CH8 heating. Include AUTO, BYPASS and mixed
positions. Use branch currents within the fuse manufacturer's ambient derating;
a fuse's printed 20 A maximum is not permission to run it at 20 A continuously.
Repeat at the declared operating ambient/cooling conditions and until thermal
steady state, then repeat hot startup and fault tests. Record current sharing
between each MOSFET pair. Stop at the reviewed case/junction/terminal limits;
those limits must be set before testing, not inferred from a component surviving.

Verify branch-fuse/PROFET coordination with the actual approved fuse series and
representative inrush/stall loads. No arbitrary motor, relay or upstream fuse is
qualified by this board-level test plan. A final installation rating also needs
the installation inputs that the owner deliberately deferred.

## Acceptance records

A prototype-fabrication release requires engineering closure and the exact source
hashes from `just verify`. A **production** release additionally requires the
recorded bench, fault, USB and thermal results above, a defined operating/load
rating, assembly inspection criteria and a functional check for each built board.
`docs/release-status.json` must distinguish these two decisions. No test results
or production rating exist yet.
