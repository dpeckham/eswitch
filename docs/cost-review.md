# Cost breakdown and design choices

20 September 2026 · USD per module · Purchasing parts for three modules

The current architecture carries a **$156.50–256 base materials allowance**,
with an arithmetic midpoint of **$206.25**. It excludes any additional cost of
the unresolved live fuse-transfer mechanism. The target is below $150, excluding
the owner's printed case. These are planning allowances, not a completed priced
BOM; only the named price anchors below have distributor listings.

## Where the money goes

| Item | Quantity per board | Allowance | What it buys |
|---|---:|---:|---|
| TPS12110A-Q1 protection/gate-driver ICs | 12 | $35–40 | Channel gate drive, current monitoring, and fast fault protection |
| Channel power MOSFETs | 24 | $24–40 | Two per channel for switching and off-state reverse-current blocking |
| Current shunts | 12 | $6–12 | Current measurement and hardware overcurrent detection |
| Channel support parts | 12 sets | $14–26 | Fault latches, temperature sensing, suppression, gate/timing parts, small passives |
| Basic fuse contacts | 36 | $5.50–8 | Three-contact AUTO/LOAD/BYPASS arrangement; live-transfer suitability unproven |
| Branch fuses | 12 | $8–14 | Physical branch protection in AUTO and BYPASS |
| AUTO-bank service fuse/holder and input protection | Shared | $18–32 | Bank isolation, reverse-polarity protection, transient suppression |
| ESP32-S3 Wi-Fi/MCU module | 1 | $6–8 | Controller and wireless connection |
| Logic power, measurement, indicators, service connection | Shared | $10–18 | Regulator, ADC/multiplexing and board support |
| Terminals and copper bus | One set | $15–28 | Twelve load connections, feeder connection, high-current distribution |
| PCB | One board allocation | $15–30 | Initial four-layer, 2 oz outer-copper allowance |
| Printed case, printed guards and supports | Owner supplied | $0 | Excluded from procurement at the owner's request |
| **Base subtotal** | | **$156.50–256** | **About $206 at the midpoint** |
| Live-transfer mechanism beyond basic contacts | Unresolved | **TBD** | May require extra carrier/contact hardware |

The first four rows total **$79–118**: approximately half the midpoint budget.
This is the main area to reconsider. Buying a cheaper Wi-Fi module cannot solve
the budget gap on its own.

The external battery feeder fuse/cabling, shipping, tax, spares, tools, test
equipment, assembly, and firmware labor are excluded. Nonprinted case fasteners
and any additional thermal hardware must be included when the final BOM is made.
PCB minimum-order quantities may make the cash purchase larger than the allocated
cost of the three installed boards. The midpoint base allowance is $618.75 for
three modules; the $150-per-board target totals $450, before these exclusions.

## Distributor price anchors

Listings checked on 20 September 2026; prices are not reserved or checkout quotes.
Purchase quantities below are for three boards, not high-volume reel pricing.

| Part | Purchase quantity / applicable listed tier | Installed cost per board |
|---|---|---:|
| [TPS12110AQDGXRQ1](https://www.digikey.com/en/products/detail/texas-instruments/TPS12110AQDGXRQ1/17748310) | 36 devices; $2.8584 each at the 25-piece tier | $34.30 for 12 |
| [Keystone 3557](https://www.digikey.com/en/products/detail/keystone-electronics/3557/2092485) | 108 contacts; $0.1518 each at the 100-piece tier | $5.46 for 36 |
| [ESP32-S3-WROOM-1-N8](https://www.digikey.com/en/products/detail/espressif-systems/ESP32-S3-WROOM-1-N8/15200089) | 3 modules; $5.66 each | $5.66 |
| Alternative [TPS2HCS10AQPWPRQ1](https://www.digikey.com/en/products/detail/texas-instruments/TPS2HCS10AQPWPRQ1/28022237) | 18 dual-channel devices; $3.081 each at the 10-piece tier | $18.49 for 6 |

## Choices that can make a material difference

These are alternatives for discussion, not changes to the agreed design.
Savings overlap and must not simply be added together.

| Choice | Quantifiable cost effect | Tradeoff / condition |
|---|---|---|
| Use six dual smart switches instead of twelve driver/shunt/discrete-switch circuits | $18.49 of core ICs versus $64.30–86.30 for the existing drivers, MOSFETs and shunts; **$45.81–67.81 gross component difference** | This is not net board saving: add the complete reverse-blocking solution, required supporting parts and thermal provisions; account for any support parts eliminated. Prove 10 A loading of adjacent channels, latch behavior, measurement accuracy, PWM, and all-OFF restart. |
| Populate ten electronic channels and leave two outputs permanently fuse-only | **About $13–20 saved per affected board**, from removing two channel-electronics sets | Keeps twelve fused outputs, but only ten are remotely switchable/measured. Fits two feeds that will remain in BYPASS anyway. Retain the fuses and terminals; do not assume this applies to all three boards. |
| Populate eight electronic channels and leave four outputs permanently fuse-only | **About $26–39 saved per affected board** | Same principle, but loses four remotely controllable outputs. Counts are alternatives to discuss, not assumed load assignments. |
| Remove off-state reverse-current blocking from all twelve electronic channels in the current discrete design | **$12–20 of MOSFETs removed**, before any supporting-circuit changes | An externally powered load could feed the AUTO bus through an OFF channel. This does not remove the separate input reverse-battery stage. Requires reviewing connected equipment and explicitly accepting the functionality change. |
| Reduce PCB area and quote alternative layer/copper/bus arrangements | Existing PCB allowance is **$15–30**; net saving unquoted | An engineering optimization that may preserve functions. Additional bus copper, soldering labor and thermal/EMI requirements can offset a cheaper bare PCB. |

The smart-switch option deserves a full comparison before dropping features.
TI documents integrated protection, sensing and PWM in the
[TPS2HCS10-Q1 family](https://www.ti.com/product/TPS2HCS10-Q1).
It is not an automatic substitute for the opposing-FET design. In particular,
the [electrical-characteristics table](https://www.ti.com/document-viewer/TPS2HCS10-Q1/datasheet/GUID-XXXXXXXX-SF0T-XXXX-XXXX-000000374227)
lists typical continuous current at 85°C ambient as 7 A per channel with both
channels active, versus 12 A with one active. Those conditions do not establish
two simultaneous 10 A channels in our enclosure. Input reverse-battery survival
also does not establish off-state reverse-current blocking.

The $13–20 and $26–39 figures are proportional estimates from the existing
$79–118 channel-electronics allowance. Shared latch packages, purchase tiers,
and actual footprints can change the result. They exclude any extra saving from
redesigning the PCB smaller. A common twelve-channel PCB could instead retain
unpopulated AUTO-stage footprints for future expansion, with unavailable AUTO
positions clearly marked.

The second MOSFET is useful for blocking backfeed while a channel is OFF in AUTO.
The proposed movable fuse already disconnects the AUTO output in BYPASS; those
are separate functions. Removing one does not mean removing the other.

## Choices with little benefit in the current architecture

- **Dropping dimming:** mostly a firmware simplification with the current driver
  and MCU. It does not remove the main power components or thermal protection.
- **Dropping current reporting:** the shunts still serve hardware fault detection,
  and the driver already includes a current-monitor output. Only part of the
  shared measurement circuitry might be removed.
- **Changing the ESP32:** the entire radio/MCU is a $5.66 component at the listed
  quantity. GPIO/PWM expansion could consume savings from a smaller module.
- **Lowering the 40 A aggregate rating again:** may reduce common copper/thermal
  requirements, but does not remove twelve complete channel circuits.

An eight-output controller would save fuse/terminal/PCB cost as well as channel
electronics, but it changes the twelve-output requirement more substantially
than leaving selected existing outputs fuse-only. It is not assumed here.

## Recommendation

First cost and qualify the dual-smart-switch architecture, and obtain a PCB quote
based on a realistic smaller placement. Keep dimming and current reporting for
now. Consider omitting AUTO circuitry only on outputs that will permanently feed
the network through BYPASS. Keep reverse blocking in the comparison until the
load connections show whether omitting it is an acceptable tradeoff.

Resolve the live fuse-transfer mechanism in parallel. Its extra cost is unknown,
not assumed zero, and every architecture must still satisfy the requirement that
other channels stay powered during an emergency transfer. No below-$150 complete
implementation is claimed by this review.
