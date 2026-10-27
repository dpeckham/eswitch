# Eight-channel eswitch — PROTO-PWR3

212 × 116 mm, four-layer prototype with shared LM74800-Q1 AUTO/logic protection
and unconditional passive fuse-selected BYPASS. Open `eswitch-simple.kicad_pro`.

The release is for **bare-board first articles and controlled bench testing**.
See [BUILD.md](BUILD.md) for assembly and ordering, and
[PROTECTION-REVIEW.md](PROTECTION-REVIEW.md) for the engineering review and
hardware tests. Neither 40 A continuous operation nor surge survival has been
qualified on hardware. Firmware is not supplied.

## Power paths

```
AUTO:   BATT_RAW -- F10 -- LM74800 cutoff -- shared VS -- PROFET -- ATO fuse -- LOAD
BYPASS: BATT_RAW ----------------------------------------------- ATO fuse -- LOAD
```

One movable ATO fuse per channel, three clips. Pins 1/2/3 are PROFET_OUT/LOAD/RAW.
Move the fuse between AUTO and BYPASS only with power disconnected; remove it for
OFF. BYPASS/OFF disconnects the load from the PROFET output, avoiding body-diode
backfeed. BYPASS has no series electronics and receives raw surges/reversed polarity.

For electronics-fault recovery, disconnect battery and USB, remove F10, move usable
channel fuses to BYPASS, then restore power. All AUTO channels may be lost; no extra
fixed per-channel fuses are required. Upstream-fuse selectivity and uninterrupted
operation are not promised. Shared copper/terminal damage is outside the model.

F10 is a removable Mersen FR14GG50V40 with two MR14SPRING clips and M5 terminals.
F9 remains the 2 A logic fuse. AUTO uses BTS7004 on CH1/2, BTS7008 on CH3–7 and
BTS7002 on CH8. Maximum ATO fuses: **10/10/5/5/5/5/5/20 A**. These are fuse maxima,
not validated continuous channel currents. LEDs show AUTO output voltage; BYPASS
current is not measured. J11–J18 pin 1 is LOAD+, pin 2 is GND. J5 is 3.3 V bench UART.

The common-source protection targets a +80 V, several-second input event using
overvoltage cutoff, not fuse operation or continuous linear clamping. Nominal cutoff
is 16.841 V. The four 200 V and two 60 V MOSFETs use individual gate resistors.
C27 is 1 µF for the parallel-bank charge pump. The existing sense resistance values
remain; R104–R804 use high-power ERJ-PA3 parts for fault-reporting dissipation.

## Verification and fabrication

- Native ERC, PCB DRC, unconnected and schematic-parity checks must all be zero.
- Topology model: 52,488 mode/supply combinations and 54 fault/removal cases.
- `power-copper-review.json`: 60 planar power paths with explicit regression floors.
- `power-transition-review.json`: real pad-layer connections and local via arrays.
- `protection-screen.json` and `sense-screen.json`: reproducible static screens.
- `out/redesign/verification.json`: source hashes and checks for the packaged revision.

The two-layer LOAD corridors, protected supply spine and raw BYPASS feed are
explicitly reserved before routing signals. Geometry checks are not thermal solvers.
Manufacturing uses JLC041622-3313, 2 oz inner and outer copper, filled/capped vias
and 90 Ω USB differential control. Follow `JLCPCB-ORDER.txt` exactly.

```
python3 redesign/generate.py  # explicitly regenerate schematic/BOM after changes
just verify                  # ERC/topology/parity/geometry/physical transitions
just package                 # verified fabrication and portable project ZIPs
just render                  # board views
```

The saved PCB is authoritative. Routing scripts and `out/redesign/protection-*`
files are development history, not alternative ordering files. Some intermediate
candidates intentionally contain errors or disconnected nets. Do not regenerate
placement over the finished board. KiCad's Python environment is required for
layout scripts; `requirements-route-gaps.txt` dependencies live in `out/py39`.

## Procurement and installation

`bom-draft.csv` is the fitted one-board BOM despite its historical filename.
`../fab/eswitch-digikey-qty1.csv` contains exact MPN/quantity upload rows, without
spares. F10 screws, washers and shims are separate mechanical purchases detailed
in BUILD.md. Stock and cart acceptance must be checked when ordering.

`cost-estimate.json` applies historical prices only where known and explicitly
lists unpriced parts. Its subtotal is **not a complete build price or current quote**.
Fabrication, assembly, hardware, shipping and taxes are excluded.

Intended installation: Vatrer 300 Ah LiFePO4, separate Victron Orion XS 12/12-70A
charger branch, 40 A MRBF eswitch feed and 75 A MRBF charger feed. Use 8 AWG copper
positive/negative for the 1 m battery run and 4 mm² positive/negative for the 3 m
pump run. CH1/2 with a provisional 10 A fuse is appropriate for the standard 12 V
Rule 1500 GPH model; confirm the actual pump. Direct-battery fault coordination,
thermal limits, pump transients and surge performance remain hardware tests.
