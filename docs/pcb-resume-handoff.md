# Revision C handoff — 2026-09-19

The owner requires single-channel fault isolation in AUTO and BYPASS, independent
of firmware. The current schematic implements eight local TPS2492 breakers and
coordinated shared startup. The board is 334 × 172 mm with twelve mounting holes.
See [channel protection](channel-isolation-review.md) and the authoritative
[release record](release-status.json) for implementation details and current status.

The saved PCB is authoritative. Do not rerun legacy migration or board-generation
scripts on it: that would replace completed placement and routing. Revision-B
Gerbers remain withdrawn. Current manufacturing exports belong in `fab/revision-c`.

The purchasing BOM contains 67 exact-MPN lines, with quantities for one assembly,
eight fuses and twelve standoffs. The purchaser applies the desired build quantity.
[BOM cost](bom-cost.md) records dated USD pricing and the optional spare-parts cart.

Before packaging, run `just verify`; ERC, DRC including warnings, unrouted items
and schematic parity must all be zero, with source-bound analytical and transient
evidence. Packaging requires a matching approved prototype release record.
Assemble one board first and complete [bring-up](bring-up.md) before assigning a
40 A continuous or marine-service rating.
