#!/usr/bin/env python3
"""Remove only native-DRC dangling copper from a separate routing candidate."""
from route_checked import *
import re


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-spine2.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-clean.kicad_pcb')
    p.add_argument('--single-pass',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--ripup-dangling-signals',action='store_true',help='Fully reroute affected IS/IN/DEN/UART nets instead of pruning long residual tails')
    p.add_argument('--allow-ripup-gaps',action='store_true',help='Permit added disconnections only for an explicit rerouting workflow')
    a=p.parse_args()
    if a.single_pass:
        report=json.loads(a.output.with_suffix('.drc.json').read_text())
        ids={i['uuid'] for v in report['violations'] if v['type'] in ('track_dangling','via_dangling') for i in v['items']}
        b=pcbnew.LoadBoard(str(a.output));retired=[]
        objects=items_by_id(b);connectivity=b.GetConnectivity()
        if a.ripup_dangling_signals:
            nets={short_name(objects[uid]) for uid in ids if uid in objects
                  and re.fullmatch(r'(?:IS|IN|DEN|ISP|INR|DENR)[1-8]|[RT]XD0',short_name(objects[uid]))}
            ids.update(t.m_Uuid.AsString() for t in b.GetTracks() if short_name(t) in nets)
            print('Signal nets cleared for rerouting:',sorted(nets),flush=True)
        # A disconnected route stub can comprise hundreds of 0.05 mm segments.
        # Remove its full component only when it reaches at most one physical
        # pad and no zone: such a component cannot interconnect any terminals.
        for uid in list(ids):
            item=objects.get(uid)
            if item is None:continue
            connected=list(connectivity.GetConnectedItems(item))
            pads={i.m_Uuid.AsString() for i in connected if i.GetClass()=='PAD'}
            if len(pads)<=1 and not any(i.GetClass()=='ZONE' for i in connected):
                ids.update(i.m_Uuid.AsString() for i in connected if i.GetClass() in ('PCB_TRACK','PCB_VIA'))
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() in ids:
                b.Remove(t);retired.append(t)
        if ids and not retired:raise RuntimeError('Native dangling items could not be matched')
        previous=a.output.read_bytes()
        previous_report=a.output.with_suffix('.drc.json').read_bytes()
        old_gap_count=len(report['unconnected_items'])
        report=check(b,a.output)
        if len(report['unconnected_items'])>old_gap_count and not a.allow_ripup_gaps:
            a.output.write_bytes(previous)
            a.output.with_suffix('.drc.json').write_bytes(previous_report)
            raise RuntimeError('Cleanup introduced disconnected copper; candidate restored for targeted trimming')
        if errors(report):raise RuntimeError('Unexpected copper error after dangling-item removal')
        a.output.with_suffix('.prune.json').write_text(json.dumps({'removed':len(retired)})+'\n')
        return
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    b=pcbnew.LoadBoard(str(a.source));report=check(b,a.output)
    if errors(report):raise RuntimeError('Fix copper errors before pruning dangling items')
    total=0
    for attempt in range(20):
        ids={i['uuid'] for v in report['violations'] if v['type'] in ('track_dangling','via_dangling') for i in v['items']}
        if not ids:break
        # Fresh KiCad Python process per pass avoids invalidating SWIG-owned
        # track containers when the previous board and retired tracks are freed.
        command=[sys.executable,__file__,'--output',str(a.output),'--single-pass']
        if a.ripup_dangling_signals:command.append('--ripup-dangling-signals')
        if a.allow_ripup_gaps:command.append('--allow-ripup-gaps')
        subprocess.run(command,check=True)
        removed=json.loads(a.output.with_suffix('.prune.json').read_text())['removed']
        total+=removed;report=json.loads(a.output.with_suffix('.drc.json').read_text())
        print(f'Pass {attempt+1}: removed {removed}; {len(report["unconnected_items"])} gaps',flush=True)
        if errors(report):raise RuntimeError('Unexpected copper error after dangling-item removal')
    else:raise RuntimeError('Dangling-item cleanup did not converge')
    a.output.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Removed',total,'dangling segments/vias; remaining gaps:',len(report['unconnected_items']),flush=True)


if __name__=='__main__':main()
