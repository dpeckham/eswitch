# eswitch build recipes. Requires: mise (kicad, java), python3.
kicad := "kicad"

# Generate everything: libraries, schematic, netlist check, ERC, board, routing, DRC, renders
all: libs sch netlist erc pcb route finish drc render

libs:
    python3 tools/gen_libs.py

sch:
    python3 tools/gen_sch.py

netlist:
    mkdir -p out
    kicad-cli sch export netlist --format kicadsexpr -o out/eswitch.net eswitch.kicad_sch
    python3 tools/check_netlist.py out/eswitch.net

erc:
    kicad-cli sch erc --severity-all -o out/erc.txt eswitch.kicad_sch

# Unrouted board with all power copper placed
pcb:
    {{kicad}} python3.11 tools/gen_pcb.py

# Auto-route signal nets with freerouting (passes optional)
route passes="30":
    {{kicad}} python3.11 tools/route.py {{passes}}

# Post-route clean-up: prune router leftovers, apply manual fix-ups, stitch GND islands
finish:
    for i in 1 2 3 4; do {{kicad}} python3.11 tools/finish.py prune && break; done
    {{kicad}} python3.11 tools/finish.py fix
    {{kicad}} python3.11 tools/stitch.py
    {{kicad}} python3.11 tools/add_models.py

drc:
    kicad-cli pcb drc --severity-all --format json -o out/drc.json eswitch.kicad_pcb
    python3 -c "import json,collections; d=json.load(open('out/drc.json')); print(dict(collections.Counter(v['type'] for v in d['violations']))); print('unconnected:', len(d['unconnected_items']))"

render:
    kicad-cli pcb render -o out/render_top.png --side top --width 2400 --height 900 --zoom 1.0 eswitch.kicad_pcb
    kicad-cli pcb render -o out/render_bottom.png --side bottom --width 2400 --height 900 --zoom 1.0 eswitch.kicad_pcb
    kicad-cli sch export pdf -o out/eswitch.pdf eswitch.kicad_sch

# Fabrication outputs (gerbers, drill, BOM, position files)
fab:
    mkdir -p out/fab
    kicad-cli pcb export gerbers -o out/fab/ --board-plot-params eswitch.kicad_pcb
    kicad-cli pcb export drill -o out/fab/ eswitch.kicad_pcb
    kicad-cli pcb export pos -o out/fab/eswitch-pos.csv --format csv --units mm --use-drill-file-origin eswitch.kicad_pcb
    kicad-cli sch export bom -o out/fab/eswitch-bom.csv --fields "Reference,Value,Footprint,MPN,Note,${QUANTITY}" --group-by Value,Footprint,MPN eswitch.kicad_sch

# Bring the generated files up to the native KiCad 10 format
upgrade:
    kicad-cli sch upgrade eswitch.kicad_sch
    kicad-cli pcb upgrade eswitch.kicad_pcb
