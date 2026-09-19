REVISION B — RELEASED FOR THREE PROTOTYPE PCBs

Upload revision-b/eswitch-revB-gerbers.zip. Production qualification remains open.
Board: 253 x 75 mm, four layers, JLCPCB JLC041622-3313, ENIG,
2 oz outer AND inner, 1.6 mm nominal (1.59 mm selected stackup).
Do not substitute stackup/copper weights: USB geometry depends on them.
CAD minima: 0.18 mm track, 0.20 mm clearance, 0.30 mm finished through-drill,
0.40 mm copper-to-edge, 0.10 mm via annular ring. These do not establish 40 A.

The package includes four copper layers, masks, silkscreens, paste, outline,
separate PTH/NPTH drills, schematic, 1:1 component-side assembly drawings,
three-board BOM, verification/source hashes and engineering release conditions.
Confirm the manufacturer's upload preview, layer order, outline dimensions,
plating and selected stackup before checkout. No order has been placed here.

Read ../docs/prototype-release.md and ../docs/bring-up.md. Assemble and validate
one board first. Full 40 A startup is not required; the 40 A continuous target
still requires physical qualification. Start with a protected laboratory source.

`mise exec -- just package` verifies the saved board and checks source-specific
release and fresh BOM evidence. It preserves the routed design. Stock observations
in digikey/ cover all three builds but are not reservations. Refresh at checkout.

Do not upload the unreleased review ZIP under ../out/review/, legacy-f76c39e/,
or the previous OSH Park files. They are superseded.
