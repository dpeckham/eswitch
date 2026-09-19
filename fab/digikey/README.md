# DigiKey BOM — quantities for ONE module

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
