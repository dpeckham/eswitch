# eswitch — 12 V Signal K load controller with fuse bypass

A fresh design for twelve remotely controlled DC outputs, up to 10 A each,
and an integrated passive fuse bypass, inspired by the Maretron CLMD12 and CBMD12.
An ESP32 Wi-Fi client connects to a Signal K server; no CAN or local switch
inputs are planned.

**Start with the [design proposal and open questions](docs/design-proposal.md).**

Confirmed: 12 V only, no paralleled outputs, and three units assembled using hot
air, with likely open-source publication later. Other channels must remain
powered during occasional emergency fuse transfers; outputs may turn off during
controller restarts. Signal K and/or Wi-Fi infrastructure will draw power through
eswitch, so those channels must start locally without waiting for the network.
The proposal identifies the unresolved live-transfer mechanism, total-current
requirement, and Signal K integration details.

Status: design document only. There is no fabrication release for this design.
The previous eight-channel schematic, PCB, purchasing files, and fabrication
packages have been removed from this worktree. They remain in Git history at
commit `d1de4a6`; their ratings and release status do not apply to this proposal.
