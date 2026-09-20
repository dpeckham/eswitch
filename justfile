# eswitch build recipes. Requires: mise (kicad, java), python3.
kicad := "kicad"

# Verify and render the saved, routed design. Never regenerate it implicitly.
all: verify render

verify:
    python3 tools/verify.py

libs:
    {{kicad}} python3.11 tools/gen_libs.py
    python3 tools/gen_models.py

sch:
    {{kicad}} python3.11 tools/gen_sch.py

netlist:
    mkdir -p out
    kicad-cli sch export netlist --format kicadsexpr -o out/eswitch.net eswitch.kicad_sch
    python3 tools/check_netlist.py out/eswitch.net

erc:
    kicad-cli sch erc --severity-all --exit-code-violations -o out/erc.txt eswitch.kicad_sch

# Create a separate unrouted layout candidate; preserve the saved routed PCB.
pcb:
    {{kicad}} python3.11 tools/gen_pcb.py --output out/generated-candidate.kicad_pcb

# Auto-route signal nets with freerouting (passes optional)
route passes="30":
    {{kicad}} python3.11 tools/route.py {{passes}}

# Guarded repair for signal gaps left by routing/migrations; not for power or USB nets.
repair-gaps:
    mkdir -p out/py311
    python3 -m pip install --disable-pip-version-check --upgrade --only-binary=:all: --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --abi cp311 --target out/py311 -r requirements-route-gaps.txt
    {{kicad}} python3.11 tools/route_gaps.py

# Checked cleanup of the saved revision-C board.
finish:
    {{kicad}} python3.11 tools/production_silk.py --board eswitch.kicad_pcb
    {{kicad}} python3.11 tools/prune_checked.py
    {{kicad}} python3.11 tools/stitch_checked.py
    {{kicad}} python3.11 tools/add_models.py

drc:
    kicad-cli pcb drc --severity-all --format json -o out/drc.json eswitch.kicad_pcb
    python3 -c "import json,collections; d=json.load(open('out/drc.json')); print(dict(collections.Counter(v['type'] for v in d['violations']))); print('unconnected:', len(d['unconnected_items'])); raise SystemExit(bool(d['unconnected_items'] or any(v['severity']=='error' for v in d['violations'])))"

# Per-board manual-assembly purchasing list; fails if stock evidence is stale/insufficient.
bom:
    python3 tools/manual_bom.py
    python3 tools/bom_cost.py

check-silk:
    {{kicad}} python3.11 tools/check_fuse_silk.py

check-board:
    {{kicad}} python3.11 tools/check_board_netlist.py

check-geometry:
    {{kicad}} python3.11 tools/check_geometry.py

# Exact native KiCad naming/metadata parity is a separate release requirement.
parity:
    kicad-cli pcb drc --schematic-parity --severity-all --format json -o out/drc-parity.json eswitch.kicad_pcb
    python3 -c "import json; d=json.load(open('out/drc-parity.json')); print('parity issues:', len(d['schematic_parity'])); raise SystemExit(bool(d['schematic_parity']))"

render:
    kicad-cli pcb render -o out/render_top.png --side top --width 2400 --height 1400 --zoom 1.0 eswitch.kicad_pcb
    kicad-cli pcb render -o out/render_bottom.png --side bottom --width 2400 --height 1400 --zoom 1.0 eswitch.kicad_pcb
    kicad-cli sch export pdf -o out/eswitch.pdf eswitch.kicad_sch

# Released bare-board upload plus exact-MPN per-board manual-assembly BOM.
package: verify release-check
    python3 tools/fab_package.py

# Same checked package entry point; no alternate unverified fabrication path.
fab: package

# Review-only CAM outputs, clearly marked and stored under out/.
review-package: verify
    python3 tools/fab_package.py --review

release-check:
    python3 tools/check_release.py

# Bring the generated files up to the native KiCad 10 format
upgrade:
    kicad-cli sch upgrade eswitch.kicad_sch
    kicad-cli pcb upgrade eswitch.kicad_pcb
