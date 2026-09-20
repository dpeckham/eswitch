# DigiKey BOM — quantities for ONE module

This is the revision-C BOM, including independent channel breakers. Check
[current release status](../../docs/release-status.json) for fabrication readiness.
[Cost per board](../../docs/bom-cost.md) includes a priced breakdown and an optional
cart with spares where price breaks reduce the total cash cost.

`eswitch-digikey-bom.csv` lists the exact parts needed to assemble **one board**.
Apply your desired number of modules when ordering. No batch multiplier or spare
allowance is included, even though the prototype plan is to build three modules.

Quantity checks: 1 ESP32 module, 24 Keystone 3557 clips, 8 output connectors,
2 input terminals, and 8 branch fuse inserts per board. The clip quantity counts
individual clips, not complete fuse holders.

For manual assembly, choose cut tape (CT) for surface-mount parts where offered,
and the listed bulk/tray packaging otherwise. Digi-Reel fees and full-reel minimum
quantities are unnecessary for this build. Check quantity breaks in the cart:
occasionally a few extra parts cost less than the exact required quantity.

`stock-audit.csv` is a dated inventory observation, not a price quote or stock
reservation. No parts have been purchased here. Installation wiring, input
ring lugs/screws and enclosure hardware are outside this component BOM.
