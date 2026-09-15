# Critical review — 2026-09-15

**HOLD the PCB order.** Confirmed part/connector/fabrication-rule corrections are
implemented, but the electrical/layout redesign is not complete. A clean ERC/DRC
does not establish 40 A capability, transient survival or safe marine service.

## Owner's requirements

Nominal 12 V boat house bank, DC–DC charged from the alternator-fed bank; no direct
starter/alternator connection. Battery chemistry/model and charger/settings remain
unknown. Total continuous target is **40 A**, not 65 A. Channel targets remain
10/10/5/5/5/5/5/20 A. Use direct-entry screw outputs and **upstream main fusing, no
onboard MIDI**. Three boards will be assembled manually with paste and hot air/hot
plate available. Exact BOM parts must be in stock at DigiKey in build quantities.

## Implemented corrections

| Finding | Correction |
|---|---|
| B360-13-F is SMC, not the fitted SMA | D1/D2/D4 use B360A-13-F. [Diodes datasheet](https://www.diodes.com/datasheet/download/B360A.pdf) |
| Output part was pluggable, not direct-entry | Eight Wuerth 691218410002 two-pole blocks, 7.62 mm pitch, pin 1 GND/pin 2 LOAD+. Component rating 30 A/pole, 24–10 AWG. [Drawing](https://www.we-online.com/components/products/datasheet/691218410002.pdf) |
| Keystone 8196 inputs were only 30 A each | Replace with Wuerth 74650195, nine solder pins, M5 blind thread. Positive and return ratings never add. New hole pattern requires local signal rerouting. [Old terminal](https://www.keyelco.com/product.cfm/product_id/1533), [replacement](https://www.we-online.com/components/products/datasheet/74650195.pdf) |
| LED resistor power margin | R107–R807 become 10 kΩ: 28²/10000 = 78.4 mW even with a shorted LED. Ambient derating still applies. |
| Fuse identification | Each channel holder has its circuit number and maximum fuse rating: CH1–2 10 A, CH3–7 5 A, CH8 20 A. F9 is marked LOGIC MAX 2A on the SMD side. Output labels identify channels without implying a qualified continuous-current rating. |
| Fabrication minima | Copper-edge clearance 0.4 mm; minimum through-drill 0.254 mm; enlarged ESP32 thermal holes; project rules now persist reliably. |
| Connectivity and parity | The terminal migration is fully routed. Native KiCad reports 0 unrouted connections and 0 schematic/PCB parity issues; the independent 497-pin assignment check agrees. |
| ESP32 antenna | Restored an all-copper/pad/via keepout over the portion of the antenna region that overlaps the PCB, moved C10/C1/C2 clear, and rerouted VIN/3V3. The module antenna remains intentionally beyond the board edge. |
| U3–U7 identification | BTS70081EPRXUMA1 is **BTS7008-1EPR**, not EPP. Correct symbol/value/datasheet. Pinout matches, but use EPR specifications: 8.8 mΩ typical, 16 mΩ maximum at 150 °C, nominal kILIS 14500. [Datasheet pp. 2, 5–6](https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7008-1epr-datasheet-en.pdf) |
| Stock/assembly | Replace unavailable same-value/package order codes, include LFS button suffix, and generate a three-board purchasing list with dated stock evidence. U11 becomes SRV05-4HTG-D, four steering channels paired externally onto two data nets. The newly unavailable CC0603KRX7R9BB104 is replaced by the same-size/value/voltage X7R Yageo CC0603JRX7R9BB104 with tighter ±5% tolerance. [Littelfuse datasheet](https://www.littelfuse.com/assetdocs/littelfuse-tvs-diode-array-srv05-4htg-d-datasheet?assetguid=d716fc4c-0484-4b67-97d8-cf719554d89a), [Yageo specification](https://www.yageogroup.com/download/specsheet/CC0603JRX7R9BB104) |

The BOM contains 46 line items including branch fuse inserts and standoffs. Its
stock observations are not reservations. See [assembly notes](assembly.md),
[stock evidence](digikey-stock.json) and `fab/digikey/`. No automatic unreviewed
cross-manufacturer substitutions are permitted.

## Order-stopping issues still open

### Input protection

SMBJ26A's specified clamp reaches 42.1 V, above the PROFET's 28 V normal absolute
maximum and 35 V **specified suppressed** load-dump allowance. “26” is not the
clamp voltage. The house-bank arrangement changes expected disturbances but does
not establish their maximum amplitude or energy. [SMBJ26A data](https://www.littelfuse.com/products/overvoltage-protection/tvs-diodes/surface-mount/smbj/smbj26a),
[PROFET limits](https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7008-1epr-datasheet-en.pdf).

The unidirectional TVS forward-biases with reversed battery polarity. No main
reverse-blocking stage is fitted. PROFET ReverseON is not board-wide reverse
protection, especially in BYPASS. F9 protects only the logic branch. Coordinate
the reverse protection, TVS, upstream fuse/holder, feeder and available bank fault
current. A candidate 50 A fuse is **not yet approved**. A PCB PTC is not a proven
substitute for battery fault interruption. Battery/charger details are needed to
validate the input envelope and charging/equalization limits.

### Buck power stage and USB-only supply

U9 is near (29.8, 9.0) mm while catch diode D4 is near (24.5, 24.5) mm. The switch
path and roughly 54 mm feedback route are not a compact converter layout. Place
input ceramic, catch diode, inductor and local ground together; keep feedback
quiet and compensation local. Recheck loop compensation and effective capacitance
after layout changes. [TI TPS54360B layout guidance](https://www.ti.com/lit/ds/symlink/tps54360b.pdf).

TPS54360B needs at least 4.5 V at VIN. A valid low USB VBUS minus D2's forward drop
falls below that requirement, so USB-only startup is not guaranteed. Correcting
the diode package does not fix this. Use a topology with guaranteed low-voltage
headroom and test startup/load steps, USB current limits and enumeration behavior.

### USB layout

U11 is about 13 mm from J4 and the data traces are not a deliberately controlled
differential pair. Move ESD protection to the connector with a short ground path,
route over continuous reference copper and verify impedance on the actual stackup.
Review series-resistor provisions near the MCU. The ESD part substitution is not
port-level ESD qualification. Initial programming is explicitly USB-only with the
house bank disconnected, so simultaneous self-powered attach is outside the agreed
operating mode. If that changes, add VBUS detection and verify detach/re-attach.
[Espressif USB guidance](https://docs.espressif.com/projects/esp-usb/en/latest/esp32s3/usb_device.html).

### Current, thermal performance and branch fuses

OSH Park standard four-layer copper is **1/0.5/0.5/1 oz**, not 1 oz everywhere or
2 oz on the top. Analyze both common source and return paths, terminal pin fields,
contact resistance, vias and signal-induced bottlenecks for 40 A. Width alone is
not proof. [OSH Park stackup](https://docs.oshpark.com/services/four-layer/).

At CH8's hot resistance limit, 20² × 4.8 mΩ is about 1.92 W in the switch alone.
The datasheet reference board's thermal resistance does not qualify this layout.
Add close thermal vias and effective spreading copper. **PROFET exposed pads are
VS, not ground.** Validate temperature rise at 40 A simultaneous load with the
worst load distribution, enclosure/ambient, inrush and fuse-clearing conditions.
[BTS7002 datasheet](https://www.infineon.com/dgdl/Infineon-BTS7002-1EPP-DataSheet-v01_11-EN.pdf?fileId=5546d46278d64ffd0178d95f93655dc0).

The ATOF derating table permits 18 A through a nominal 20 A fuse at 20 °C and 15 A
at 65 °C; a 10 A fuse permits 8 A at 65 °C. Printed fuse ratings are therefore not
continuous channel ratings. Do not simply upsize: review wire, holder, terminals,
copper, inrush and clearing time first. [Littelfuse ATOF table](https://www.littelfuse.com/assetdocs/littelfuse_datasheet_287_atof_r2.7.pdf?assetguid=43dcdce8-8ca2-426f-8998-7e566f048d40).

### Physical fit

Print custom footprints at 1:1 and check real clips, a blade fuse and both terminal
types. The direct-entry row is taller/deeper and overhangs the edge; input hardware
needs a validated lug/screw stack and strain relief. Generated 3D envelopes do not
prove pin tolerances, fuse retention or screw access. See [assembly.md](assembly.md).

## Additional checks

- Review each variant's application network, including the absent 47 nF
  VS-to-device-GND capacitor. Device GND is separated from board GND by RGND.
- Off-state open-load diagnosis needs the external pull-up/test circuit, which is
  absent. Do not promise it in firmware/UI. Calibrate current sensing and use
  variant-specific limits rather than one nominal kILIS for every channel.
- Check repetitive inductive turn-off energy and cable inductance. Internal clamps
  are not unlimited. Verify OFF states through reset, programming and brownout.

## OSH Park approval-page notes

The [submitted approval page](https://oshpark.com/uploads/11HAlFYE/approval/new)
is a prior-revision manufacturing preview, not electrical approval. Its notes cover
closed outlines, plating where holes intersect copper, unsupported blind/buried or
overlapping holes, drill-size adjustment and silk clipping at exposed copper/edges.
The rendered layers/outline do not qualify current capacity or component choices.

The original 0.2 mm module drills and 0.3 mm copper-edge spacing conflicted with
the service's 0.254/0.381 mm limits; the project now uses 0.254/0.4 mm. Reinspect
layer order/polarity, finished holes, annular rings, slots and clipped labels on a
**new upload after all fixes**. Do not order the existing upload for this revision.
[OSH Park rules](https://docs.oshpark.com/services/four-layer/).

## Release conditions

Current routed snapshot: ERC reports 0 violations; copper DRC reports 0 errors and
0 unrouted items; native schematic/PCB parity reports 0 issues; the independent
assignment check matches all 497 physical pins; and the fuse-silk checker verifies
all eight circuit/max-fuse labels plus the 2 A logic-fuse label.

The 26 remaining DRC warnings were inspected: two are the intentionally clipped
silk outline of the overhanging U10 antenna, one is the deliberately modified U10
footprint (larger thermal drills/body-only courtyard), 14 are duplicate outline
ends where adjacent output-terminal bodies touch, and nine are cosmetic reference
text/outline or mask clipping on the SMD side. None involves copper clearance or
the fuse labels. They should still be reinspected on the final vendor preview.

The PCB/database checks and final plots now pass their release recipes. Close the
remaining electrical/layout and physical-fit blockers before producing a prototype
order. The owner has deferred bench testing; it remains required before claiming
continuous ratings or marine-service suitability. Fabrication is gated by
`release-status.json`; archived packages are not current releases.
