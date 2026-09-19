# Revision B handoff — 2026-09-19

**Ready to order three prototype PCBs. Production qualification remains open.**
The [release record](release-status.json) binds the approval to verified sources.
The [prototype release](prototype-release.md) records engineering assumptions,
owner decisions and controlled bench limits. The September 16 checkpoint under
`history/` describes a superseded state, not the current routed board.

## Completed

- Main schematic and 253 × 75 mm PCB agree; the TPS2492 latch-off stage is routed.
  The saved board is authoritative. Do not rerun migration or regenerate routing.
- Saved-board verification covers ERC, DRC, parity, independent pin/value/MPN
  checks, fuse silk, stackup, antenna keepout and sampled USB ground coverage.
- Buck output capacitors are exact-model GCM32ER70J476KE19L: 59.05 µF screened
  capacitance after tolerance/reserve against 40 µF required. Hardware tests follow.
- Owner accepted lower-load startup latch-off with 40 A continuous target retained.
  Fitted power/timer values remain unchanged. Analytical lower-envelope and
  twelve transient sensitivity cases support the bounded prototype release.
- Single-pass-FET SOA uses derated published curves, no equal sharing assumption,
  a 60 °C mounting-base limit and complete event duration. Clamp coordination
  and fixture restrictions are recorded; live-short/installation energy is unqualified.
- Owner confirmed both actual fuse/clip positions and both connector types fit.
  Four-layer CAM and separate 628 PTH/6 NPTH drills were independently reviewed.
- All 55 exact-MPN BOM lines cover three builds in the September 19 stock audit.
  Inventory is not reserved. Assembly PDFs show each component side at 1:1.

## Order and validate

Use `fab/revision-b/eswitch-revB-gerbers.zip` and the BOM under `fab/digikey/`.
Order four layers, JLCPCB JLC041622-3313, ENIG, 2 oz outer AND inner, 1.6 mm nominal.
Check the vendor upload preview against the package before checkout; no vendor
preview, purchase or fabrication order has been completed here.

Assemble one board first. Follow [bring-up.md](bring-up.md) and
[input-clamp-review.md](input-clamp-review.md): protected laboratory source,
staged current increases and captured waveforms before any high-energy test.
Production gates are physical startup/fault/reset/clamp results, USB/regulator
checks, measured 40 A thermal performance, and finished-board acceptance.
Installation inputs deliberately deferred by the owner remain unspecified.

## Reproduce

```sh
mise exec -- just verify
python3 tools/buck_analysis.py --check
python3 tools/input_stage_analysis.py --check
python3 tools/input_stage_transient.py --check
python3 -m unittest discover -s tools -p 'test_*.py'
mise exec -- just package
```

The transient study can be rerun with `--run` using numpy and the locally
configured ngspice/PSpice compatibility setup. The pinned TI controller model is
fetched from TI when absent; the proprietary model itself is not redistributed.
The saved result includes model/netlist hashes and assumptions.

Verification hashes include engineering release documents, source files and
reports. Review snapshots under `out/review/`, old OSH Park uploads and
`fab/legacy-f76c39e/` are not current fabrication packages. Changes remain local;
no commit, push, order or purchase was made in this continuation.
