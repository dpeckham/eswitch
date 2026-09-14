# Three-board manual assembly

Agreed method: solder paste with hot air or a hot plate is available. Exposed-pad
devices remain on the BOM; this is not an iron-only design. Procurement is through
DigiKey, with enough stock for three complete boards at the recorded check date.

`just bom` produces a three-board purchasing CSV and an inventory evidence CSV in
`fab/digikey/`. Quantities are minimum build quantities, **without spares**. For
small passives, ordering a few extra is sensible. No purchase has been made.
The dated audit is not an inventory reservation; refresh it at checkout and after
any circuit changes. The BOM describes the current design, not an approved release.

## Assembly sequence

1. Start with one board. Inspect the bare PCB and check resistance between supply
   and ground before applying power. Keep the other two unassembled until bring-up.
2. Populate the bottom-side SMD with controlled paste volume. Reflow the exposed
   pads on U1-U9 and the ESP32 module ground pad; an edge fillet alone does not prove
   a sound underside joint. Follow the component moisture/reflow requirements and
   the paste manufacturer's measured temperature profile. Hot-plate dial temperature
   is not the solder-joint temperature. Support the overhanging ESP32 antenna.
3. Inspect pin bridges and polarity under magnification. Assemble the top-side
   BOOT/RESET switches without remelting unsupported bottom-side parts.
4. Fit through-hole connectors, fuse clips and input terminals last. Large copper
   pours and REDCUBE terminals require board preheat and a sufficiently powerful,
   temperature-controlled iron. Do not increase temperature/dwell indefinitely.
5. Use a current-limited bench supply for initial logic bring-up, with no branch
   fuses/loads installed. Verify 3V3, reset, programming and all OFF states first.
   Do not perform initial short-circuit or reverse-battery tests on a house bank.

## Counts and mechanical checks

Each F1-F8 symbol represents **three** Keystone 3557 clips: 24 clips per board,
**72 clips for three boards**, plus 24 branch fuse inserts. Install only one fuse
per three-clip cell. Move the fuse between AUTO and BYPASS only with power removed.

Each board uses eight Wuerth 691218410002 output blocks: **24 blocks total**.
Pin 1 is ground; pin 2 is the positive load output. The body is 21.5 mm tall and
overhangs the PCB's output edge by approximately 2.7 mm. Check the enclosure and
tool/wire-entry access with actual parts. The manufacturer's EU and UL terminal
torque entries differ; do not blindly convert one into the other. Consult the
[output drawing](https://www.we-online.com/components/products/datasheet/691218410002.pdf).

J2/J3 use Wuerth 74650195 M5 blind-thread terminals: **six total**. All nine pins
must be soldered. Their 85 A component rating at 20 °C is conditional on the PCB,
lug and cable; it does not rate this board. The thread is 4 mm deep and tightening
torque is 2.2 N·m. Choose screw length for the actual lug/washer stack without
bottoming the screw; screws/lugs are not included in the component BOM. Provide
cable strain relief so these soldered terminals do not carry cable bending loads.
See the [input drawing](https://www.we-online.com/components/products/datasheet/74650195.pdf).

Before ordering PCBs, print both connector footprints and the three-clip fuse
footprint at 1:1 and fit real parts. The clip footprint uses **1.7 mm finished
holes**, not the old README's 1.6 mm claim. Generated 3D bodies are inspection
envelopes, not dimensionally complete manufacturer models.

## Installation is not yet specified

No onboard main fuse or MIDI holder is planned. The upstream fuse, holder, feeder,
ring lugs, M5 fastening stack, enclosure screws and strain relief must be specified
for the actual bank and installation. A 50 A upstream fuse is only a candidate,
not approved merely because the total-load target is 40 A. Battery fault interrupt
rating, conductor protection, temperature and clearing time still need review.
Do not use this unqualified board for bilge pumps or other life/safety-critical loads.
