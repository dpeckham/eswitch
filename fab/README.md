# PROTO-PWR3 prototype fabrication files

Upload **`eswitch-simple-jlcpcb-gerbers.zip`** for the 212 × 116 mm bare PCB.
Use the included `JLCPCB-ORDER.txt`: four layers, JLC041622-3313, 2 oz inner/outer,
ENIG, green mask, epoxy-filled/copper-capped vias, 90 Ω differential USB.

- `eswitch-simple-fabrication.zip`: CAM files, assembly/dimensions, BOM, engineering
  review, verification and SHA-256 manifest.
- `eswitch-simple-project.zip`: matching editable KiCad project and local libraries.
- `eswitch-digikey-qty1.csv`: exact fitted one-board MPN quantities, no spares.
  Stock/cart acceptance is unverified. F10 screws/washers/shims are separate hardware.
- `board-top.png` / `board-bottom.png`: board views; some custom components lack
  3D models. Follow assembly drawings and MPNs, not render envelopes, for fitting.

These replace DRAFT-PWR2. Release is for first articles and controlled bench tests,
not qualified battery installation. See `../redesign/BUILD.md` and
`../redesign/PROTECTION-REVIEW.md` before assembly.
