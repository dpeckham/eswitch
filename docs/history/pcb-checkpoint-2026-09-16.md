# PCB work checkpoint — paused 2026-09-16

The owner requested documentation, a commit and GitHub push, then a pause.
**NOT READY TO ORDER. No fabrication release, PCB order or parts purchase.**
Resume the existing work; do not repeat the owner decisions.

## Decisions already made

- 40 A simultaneous continuous **design target**, not a measured/qualified rating.
- Approved operating-input range **9.5–16 V**; reverse blocking and OV disconnect
  around 17 V. Higher-voltage charging/equalization may disconnect the outputs.
- Mixed AUTO/BYPASS positions at startup are required. Do not assume unloaded
  startup or ask the owner to move fuses live.
- Excessive startup current/input overcurrent must latch off until battery power
  is cycled; no timed automatic retry or firmware-dependent protection.
- Upstream main fuse, no onboard MIDI/main fuse. F9 protects the logic branch.
- Enlargement and heavier copper are approved. Selected service/stackup:
  JLCPCB JLC041622-3313, four layers, 2 oz outer and inner, nominal 1.6 mm, ENIG.
- Three boards to assemble by hand, with paste/hot air/hot plate available. Exact
  BOM parts must be in DigiKey stock in the required quantities.
- Direct-entry screw outputs. Channel maximum fuses 10/10/5/5/5/5/5/20 A;
  F9 maximum 2 A. Circuit number and maximum fuse size on silk.
- USB only for initial bench programming **with the battery disconnected**;
  subsequent firmware updates OTA.
- Battery/charger, installation, enclosure/cooling and exact loads remain
  deliberately unspecified. Do not turn these unknowns into verified ratings.
- Host PC freezes remain unresolved. PC hardware testing is deferred.
  Preserve crash-resistant saves. PCB prototype validation is still required.

## Exact file state

| Artifact | Checkpoint state |
|---|---|
| `tools/design.py`, generated schematic and custom symbol library | New TPS2492 input stage implemented; last ERC report had zero messages |
| `eswitch.kicad_pcb` | **221 × 75 mm**, older input stage; retained routed revision-B work, NOT matching the new schematic |
| `tools/input_stage.py`, `gen_pcb.py`, `layout_revision_b.py` | New stage source targeting **253 × 75 mm**; latest routing edits not successfully generated/verified |
| `tools/migrate_input_stage.py` | In-progress migration preserving channel/MCU routing; currently has an intermittent KiCad/SWIG failure |
| `fab/digikey/` | 55-line exact-MPN BOM and stock audit for three builds, observed 2026-09-16; not a reservation or release |
| `docs/release-status.json` | Explicitly blocked; stale historical zero-DRC/parity values replaced with unknowns |
| Old Gerber ZIPs / OSH Park upload | Obsolete; do not order |

Tracked PCB checkpoint SHA-256:

`6482993dbfc8724b58c9914ae6316859a5164590e9f5e608c9476d0aa4b7ba22`

At pause, `out/revb-before-latch.kicad_pcb` has the **same hash** as the tracked
PCB. Migration reads that fixed snapshot and writes only
`out/latch-candidate.kicad_pcb`. Recreate the snapshot from this commit's tracked
PCB on a fresh checkout; it is not an additional uncommitted design. Its matching
project snapshot is also under `out/`.

`out/` is ignored scratch data, not release source. The latest successfully saved
candidate and its `out/latch-drc.json` precede the newest source edits. That DRC
reported **19 unconnected items** and numerous copper errors (41 shorting-item,
24 clearance and 16 crossing reports, plus other types). These counts describe
the stale candidate only, not the tracked board or latest generator.
**Do not promote it.**

## Implemented work preserved

- TPSM63603 fixed-3.3 V buck-module circuit, custom TI footprint, compact local
  power layout and AGND net tie. Effective output capacitance still needs proof.
- USB-only LM74800 ideal-diode feed, USB ESD and deliberate differential routing;
  selected heavy-copper stackup and USB reference-plane keepouts.
- Local PROFET decoupling/input networks, wider copper and revised placement.
- Reverse-input and hardware latch-off circuit, shunt footprint and new stock
  evidence. See `docs/input-protection-review.md` for selected parts and values.
- Atomic PCB writes in `tools/pcb_io.py`, native net/metadata handling, project
  fabrication-rule persistence, and guarded low-speed signal-gap repair.
- Updated schematic, libraries, BOM and dated DigiKey/manufacturer evidence.

## First issue on resume: migration

Two identified bugs were fixed and verified in an earlier successful candidate:

1. KiCad `GetStart()`/`GetEnd()` expose live C++ vectors. Modifying a segment
   before copying both endpoints made a 32 mm inserted bridge become 64 mm.
   Endpoints are now copied by numeric value before mutation.
2. Moved zone outlines retained obsolete filled polygons. Connectivity through
   stale fills changed some retained vias to GND. All fills are now cleared before
   rebuilding connectivity; retained-net assertions surround connectivity/fill.

However, the **latest** attempt failed before saving at `board.GetNetsByName()`:

```
AttributeError: 'SwigPyObject' object has no attribute 'NetsByName'
```

It also printed many SWIG wrapper leak warnings. An earlier similar failure
occurred accessing footprint references. Retaining detached track wrappers helped
previously but did not make mutation reliable. The saved source now includes
`translated_source()`, an S-expression geometry/removal transform followed by a
KiCad reload, with the former SWIG mutation loops disabled. This workaround has
**not** had a successful verification run in the checkpoint. Do not claim the
failure is resolved. Review/test the transform and then remove obsolete disabled
code. KiCad 10 board net entries use names, not old numeric-net assumptions;
preserve footprint-local coordinates and board-level zone geometry.

Latest unverified edits rotate U14 and D7 to 270 degrees, move passives/F9 and
rewrite stage routes. Migration leaves selected bridges through the new stage
open where Y < 50 mm for guarded rerouting; existing signal ends are retained.
Check actual pad positions before trusting hard-coded fanout.
`out/latch-pads.json` is stale until a successful new run. Historical `obsolete_*`
functions remain; remove them only after the active implementation is proven.

## Remaining work, in order

1. Make migration repeatable; verify retained nets, footprint identities and
   inserted geometry. Resolve stage shorts, clearance, courtyard and mask
   conflicts. Do not overwrite the tracked board with a worse candidate.
2. Complete TPS2492 worst-case current/power limit, UV/OV threshold, timer, loaded
   startup and **single-FET hot SOA** analysis. Do not assume parallel MOSFETs
   share linear-mode startup. Verify clamps, inductance and fast-short gate
   behavior. Deep UVLO/UVEN brownout resets the latch; it has no nonvolatile memory.
3. Finish low-speed signal gaps and GND islands. Before migration, the tracked
   board's latest local report had nine gaps: six GND islands, ISP3, INR2 and IN3.
   Those are not the new candidate's gap count.
4. Check **both** 40 A positive and return paths, source/drain/shunt necks,
   copper/via current transfer, and CH8 thermal paths. Fuse limits are not
   continuous-current ratings. Define prototype thermal/startup/fault tests.
5. Verify buck effective capacitance with manufacturer DC-bias data. Four
   GRM32ER71A226KE20L 22 µF capacitors are fitted; nominal 88 µF does not prove
   effective minimum. Verify USB bench startup/current budget and continuous In2
   GND reference under the B.Cu USB pair.
6. Fresh ERC, native DRC, schematic parity, independent pin-net comparison,
   antenna/reference-plane review, fuse silk and mechanical drawing review.
   Physical fit/thermal tests are prototype bring-up, not completed results.
7. Update `justfile`, legacy finish/stitch and packaging. `tools/fab_package.py`
   still targets the old OSH Park board. **Do not run `just all` or legacy
   finish/stitch blindly**; they can replace carefully migrated routing.
   Strengthen release checks with fresh artifact evidence.
8. Update assembly docs (new buck, heavy copper, thermal pads, Wuerth THR input
   terminal process), refresh stock if stale, generate and visually inspect
   Gerbers/drills/outline/silk and an unambiguous JLC order specification.
9. Only after closure: approve prototype fabrication, commit/push and hand off
   checked upload. Do not claim tested marine suitability.

## Local tools and evidence

- KiCad 10.0.6 through mise/AppImage: `mise exec -- kicad python3.11 tools/...`.
  Limit CPU-heavy work if useful (`taskset -c 0,1`); do not troubleshoot the PC now.
- KiCad Python NumPy: `out/py311`; host PDF/scientific helpers:
  `out/review-python`. Ignored dependencies can be recreated as needed.
- `tools/route_gaps.py` is for permitted low-speed signals, **not** power paths,
  USB impedance routing or blindly connecting GND islands.
- `docs/fabrication-stackup-evidence.json` records manufacturer calculator output.
  B.Cu USB nominal width/gap 0.235/0.215 mm for selected 90 Ω stackup;
  do not substitute stackup without recalculating.
- Downloaded PDFs under `out/datasheets/`: `tps2492.pdf`, `psmn1r8-80sse.pdf`,
  `css4j-4026.pdf`, and prior evidence. Manufacturer URLs are in reviews/BOM.
  `out/nexperia-soa.png` and `out/shunt-land.png` are useful drawing references.
- Interpret Nexperia red/black SOA curves correctly before deriving a hot-case
  limit; do not substitute the headline package power rating.
- Last saved ERC report: 2026-09-16 08:48:46, zero errors/warnings. It does not
  validate the mismatched PCB or new layout.

Four randomized `.eswitch-*.kicad_pro` sidecars from earlier atomic saves were
removed during checkpoint cleanup. The real project remains; no source design
or routed PCB was removed.

Checkpoint checks: `git diff --check`, Python source compilation and independent
netlist validation passed. Regenerated BOM audit passed for 55 lines/three builds.
The release checker rejected fabrication as intended. No new full DRC/parity or
physical tests were run for this pause-and-save request.
