# eswitch — eight-channel house-bank load switch

ESP32-S3 controlled high-side switch with one ATO fuse per channel. Each three-clip
holder accepts a fuse in AUTO (through the PROFET) or BYPASS (direct to the load).

**PCB ORDER ON HOLD.** The [critical review](docs/critical-review.md) identifies
remaining input-protection, buck/USB, antenna, thermal and fuse-coordination issues.
A clean ERC/DRC does not close these engineering blockers. Old fabrication files
and the existing OSH Park upload are not approved for this revision.

## Agreed constraints

| Item | Requirement |
|---|---|
| Supply | Nominal 12 V boat house bank, DC–DC charged; battery/charger limits to be confirmed |
| Simultaneous load | **40 A continuous target**, not a qualified rating or 65 A total |
| Channels | CH1–2: 10 A target, BTS7004-1EPP; CH3–7: 5 A, BTS7008-1EPR; CH8: 20 A, BTS7002-1EPP |
| Main fuse | Upstream protection; no onboard MIDI/main fuse; F9 is logic-only |
| Outputs | Eight Wuerth 691218410002 direct-entry blocks; pin 1 GND, pin 2 LOAD+ |
| Inputs | Two Wuerth 74650195 M5 ring-lug terminals; component rating is not board rating |
| Assembly | Three boards, manual; paste + hot air/hot plate for exposed pads |
| Procurement | Exact DigiKey-stocked parts for all three builds; recheck at checkout |
| PCB | 181 × 57.5 mm, four layers; OSH Park 1/0.5/0.5/1 oz, nominal 1.6 mm |

Each channel holder is marked with its circuit number and maximum fuse value
(for example, `CH1 MAX FUSE 10A`). These are not guaranteed continuous currents.
The separate logic fuse is marked `LOGIC MAX 2A` on the underside.

## Files and checks

- [Critical review and sources](docs/critical-review.md)
- [Manual assembly and physical fit checks](docs/assembly.md)
- [Three-board DigiKey BOM](fab/digikey/eswitch-digikey-bom.csv) and
  [dated stock evidence](fab/digikey/stock-audit.csv)
- `tools/design.py`: circuit, exact order codes and schematic placement.
- `tools/gen_libs.py`, `gen_sch.py`, `gen_pcb.py`: generators. The PCB generator still
  contains the open layout issues in the review; regeneration does not fix them.
- `eswitch.kicad_pro`: open in KiCad 10. `out/`: untracked reports/renders.

```sh
mise install
mise exec -- just bom       # quantities for 3 boards; rejects stale/missing stock evidence
mise exec -- just netlist erc drc
mise exec -- just check-silk
mise exec -- just render
mise exec -- just all       # deliberately replaces the PCB and routing
mise exec -- just fab       # blocked until electrical review is closed
```

Firmware must implement safe reset states and variant-specific calibration/fault
handling. USB-only power, self-powered USB attach behavior and off-state open-load
diagnosis are not guaranteed by the current circuit.
