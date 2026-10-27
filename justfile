# Work only on the saved prototype design; generation is always explicit.
default:
    @just --list

verify:
    python3 redesign/verify.py

redesign-check: verify

package:
    python3 redesign/export.py
    python3 redesign/check_package.py

fab: package

drc:
    python3 redesign/native.py redesign/eswitch-simple.kicad_pcb --parity

render:
    python3 -c "import sys; from pathlib import Path; sys.path.insert(0,'redesign'); from native import run,OUT; Path('fab').mkdir(exist_ok=True); [run(['pcb','render','--width','1500','--height','1200','--zoom','0.95','--side',side,'--output',f'fab/board-{side}.png','redesign/eswitch-simple.kicad_pcb'],OUT/f'render-{side}.log') for side in ('top','bottom')]"

# Rebuild the schematic/BOM only when intentionally changing the circuit.
schematic:
    python3 redesign/generate.py
    python3 redesign/verify.py
