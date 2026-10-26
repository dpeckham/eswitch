#!/usr/bin/env python3
"""Run the existing connectivity-guarded pruner with native KiCad filling."""
from route_checked import *
import prune_checked


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('board',type=Path)
    a=parser.parse_args();path=a.board.resolve()
    native=OUT/'power-prune-native.kicad_pcb'
    native.with_suffix('.kicad_pro').write_text(path.with_suffix('.kicad_pro').read_text())
    # The older pruning helper fills via SWIG by default. Use the native CLI,
    # preserving its transactional connectivity checks and safe-chain analysis.
    prune_checked.router.drc=lambda board:check(board,native)
    sys.argv=['prune_checked','--board',str(path),'--max-passes','100']
    prune_checked.main()
    board=pcbnew.LoadBoard(str(path));report=check(board,path)
    path.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Violations:',report['violations'],'gaps:',len(report['unconnected_items']))


if __name__=='__main__':main()
