# Revision C prototype fabrication scope

The authoritative approval and exact source hashes are in
[release-status.json](release-status.json). Approval requires a passing saved-design
verification manifest and closure of the listed fabrication blockers. This document
alone does not release a board. Revision-B Gerbers are withdrawn and historical.

The release scope is prototype bare-board fabrication and three manual
assemblies, with one assembled and validated first. No measured 40 A continuous
or installation rating exists. Hardware measurements follow delivery; they are
not prerequisites to ordering a correctly reviewed prototype.

Revision C adds eight independent TPS2492 hardware latches ahead of AUTO and
BYPASS. [The circuit review](channel-isolation-review.md) records protection
settings, startup envelope, semiconductor stress, monitoring and layout changes.
The common protection remains as startup control and backup for shared faults.

Order **334 × 172 mm, four layers, JLC041622-3313, ENIG, 2 oz outer and inner,
1.6 mm nominal**. Preserve the USB reference stackup and geometry. The package
contains separate PTH/NPTH drills, all copper/mask/silk/paste layers, a schematic,
1:1 assembly drawings, the exact one-board BOM and its price breakdown. Select
an offered bare-board batch quantity covering the planned three assemblies.

Select **90 ohm differential impedance control, +/-10%**, and include the supplied
`USB-impedance-request.jpg`. Select **Confirm Production File**, with automatic
confirmation disabled. JLC now offers **Plugged** as its free replacement for
Tented: the order notes restrict ink plugging to eligible closed-mask 0.30/0.40 mm
via holes. Preserve exposed thermal-pad openings, solderable component holes and
NPTH holes. Thermal vias under pads remain open for this manual prototype build.
These settings follow JLC's [via process instructions](https://jlcpcb.com/help/article/pcb-via-covering).

The startup envelope is 9.5–16 V with at most 1000 µF actual capacitance per
branch, plus a resistor drawing 10 A at full voltage on CH1/2/8 or 5 A on CH3–7.
CH8 retains its 20 A maximum fuse but has a lower startup-load allowance.
A shorted branch must not prevent otherwise admissible healthy loads starting.
Constant-power converters, motors, cable impedance and residual TIMER charge
need the explicit tests in [bring-up.md](bring-up.md).

The connector and three-clip footprints retain the owner's earlier physical-fit
confirmation. The USB edge alignment, added mounting holes and enlarged outline
are new. Inspect actual manufactured-board mating and enclosure access on delivery.
JLC's public upload parser recognized four layers and a 334 × 172 mm board on
2026-09-19. Its detailed Gerber viewer requires sign-in; order-specific engineering
DFM and production-file approval remain order steps. Independent local CAM parsing
and visual inspection are recorded separately in the release evidence. No parts
or boards have been purchased by this work.

Production approval requires recorded fault/isolation, recovery, USB, regulator,
thermal and mechanical results, plus the installation/load specification deferred
by the owner. Keep that separate from prototype fabrication approval.
