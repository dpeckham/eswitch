# eswitch — 12 V Signal K load controller with fuse bypass

A fresh design for twelve remotely controlled DC outputs with an integrated
passive fuse bypass, inspired by the Maretron CLMD12 and CBMD12. Design targets
are 10 A per channel and 40 A continuously in aggregate.
An ESP32 Wi-Fi client connects to a Signal K server; no CAN or local switch
inputs are planned.

**Start with the [design proposal and agreed requirements](docs/design-proposal.md).**

Confirmed: 12 V only, no paralleled outputs, and three units assembled using hot
air, with likely open-source publication later. Other channels must remain
powered during occasional emergency fuse transfers. All electronic outputs start
OFF with no state memory; eswitch-powered network equipment stays in passive
BYPASS. Supply is a house-only 300 Ah LiFePO₄ bank charged by solar MPPT. The owner
writes the firmware for Signal K/WilhelmSK and makes a passively cooled, ventilated
printed case for a dry interior installation.

The target is below $150 per board/components, excluding the owner-supplied case.
The current allowance exceeds that target; component costs and the live fuse
transfer mechanism remain engineering work.

Status: design document only. There is no fabrication release for this design.
The previous eight-channel schematic, PCB, purchasing files, and fabrication
packages have been removed from this worktree. They remain in Git history at
commit `d1de4a6`; their ratings and release status do not apply to this proposal.
