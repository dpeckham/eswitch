PCB ORDER ON HOLD — NOT A RELEASE PACKAGE

digikey/ contains the current exact-MPN purchasing list for three manually
assembled boards, with dated inventory evidence. This is not a purchase or a
reservation; stock and the design can change before the review is closed.

legacy-f76c39e/ preserves obsolete Gerbers and vendor assembly files unchanged
for historical reference. DO NOT ORDER THEM. They do not match the corrected
components, terminals, drill/edge rules, or circuit-number/max-fuse silkscreen.
Their embedded fabrication notes are also obsolete.

See ../docs/critical-review.md for the outstanding electrical, routing, thermal,
fuse-coordination and mechanical checks, and ../docs/assembly.md for manual
assembly constraints. The existing OSH Park upload is not this revision.

The intended OSH Park standard four-layer stackup is 1/0.5/0.5/1 oz, not 1 oz on
every layer. Current constraints include 0.254 mm minimum finished through-drill
and 0.4 mm copper-to-edge clearance. These do not establish 40 A capability.

New fabrication outputs are blocked by tools/check_release.py. After all release
conditions are met, use `mise exec -- just package`; do not reuse legacy outputs.
