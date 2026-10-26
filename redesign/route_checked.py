#!/usr/bin/env python3
"""DRC-transactional local/long signal routing using the existing C++ grid search.

No SWIG copper filling. The native KiCad process fills/checks every accepted batch.
Power/USB routes are untouched and In1 remains a continuous ground reference.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'out/redesign'
sys.path.insert(0,str(ROOT/'out/py39'))
sys.path.insert(0,str(ROOT/'tools'))
os.environ.setdefault('KICAD_STOCK_DATA_HOME','/Applications/KiCad/KiCad.app/Contents/SharedSupport')
import wx
app=wx.App(False)
import pcbnew
import route_gaps as router
from pcb_io import save_board
from pcb_nets import short_name
from gen_pcb import V,apply_rules

router.W,router.H=228.0,90.0
router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
router.SIZE=router.NX*router.NY
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'


class AliasBoard:
    def __init__(self,b,inner_crossing=False,compact_crossing=False):
        self.board=b;self.inner_crossing=inner_crossing;self.compact_crossing=compact_crossing
    def __getattr__(self,k): return getattr(self.board,k)
    def FindNet(self,name): return self.board.FindNet(name) or self.board.FindNet('/'+name)
    def Zones(self):
        return [z for z in self.board.Zones() if not (
            not z.GetIsRuleArea() and z.GetLayer()==pcbnew.In2_Cu
            and ((self.inner_crossing and short_name(z) in ('LOAD1','LOAD2'))
                 or (self.compact_crossing and short_name(z) in ('BATT_RAW','LOAD1','LOAD2','LOAD5','LOAD6'))))]


def check(board,target):
    for zone in board.Zones():
        if not zone.GetIsRuleArea():zone.UnFill()
    save_board(target,board)
    report=target.with_suffix('.drc.json')
    result=subprocess.run([CLI,'pcb','drc','--refill-zones','--save-board','--severity-all','--format','json',
                           '-o',str(report),str(target)],capture_output=True,text=True)
    target.with_suffix('.drc.log').write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(f'Native DRC failed; see {target.with_suffix(".drc.log")}')
    return json.loads(report.read_text())


def items_by_id(b):
    result={i.m_Uuid.AsString():i for i in b.GetTracks()}
    result.update({p.m_Uuid.AsString():p for fp in b.GetFootprints() for p in fp.Pads()})
    result.update({z.m_Uuid.AsString():z for z in b.Zones() if not z.GetIsRuleArea()})
    return result


def errors(report): return [v for v in report['violations'] if v['severity']=='error']


def signal_count(report):
    return sum(any('[/GND]' not in i['description'] for i in gap['items']) for gap in report['unconnected_items'])


def ground_stitch(b,report):
    """Connect disconnected SMD ground pads locally to In1, with raster clearances."""
    gnd=b.FindNet('/GND') or b.FindNet('GND')
    blocked,via_blocked=router.obstacles(AliasBoard(b),gnd.GetNetCode(),.25,.6)
    objects=items_by_id(b)
    pads={}
    for gap in report['unconnected_items']:
        if not all('[/GND]' in i['description'] for i in gap['items']): continue
        for entry in gap['items']:
            item=objects.get(entry['uuid'])
            if item and item.GetClass()=='PAD' and item.GetAttribute()==pcbnew.PAD_ATTRIB_SMD:
                pads[item.m_Uuid.AsString()]=item
            elif item and item.GetClass()=='ZONE':
                # DRC names zone outlines for disconnected filled islands, not
                # necessarily the pads within those islands.
                for fp in b.GetFootprints():
                    for pad in fp.Pads():
                        if pad.GetNetCode()==gnd.GetNetCode() and pad.GetAttribute()==pcbnew.PAD_ATTRIB_SMD:
                            pads[pad.m_Uuid.AsString()]=pad
    added=[]
    for pad in pads.values():
        x,y=router.xy(pad.GetPosition())
        layer=pad.GetLayer()
        if layer not in router.LAYERS: continue
        layer_index=router.LAYERS.index(layer)
        offsets=[(0,0)]+[(r*math.cos(a*math.pi/4),r*math.sin(a*math.pi/4)) for r in (.8,1.2,1.6,2,2.4) for a in range(8)]
        for dx,dy in offsets:
            vx,vy=round(x+dx,1),round(y+dy,1)
            if any(math.hypot(vx-ax,vy-ay)<.9 for ax,ay in added): continue
            col,row=round(vx/router.STEP),round(vy/router.STEP)
            if not(0<=col<router.NX and 0<=row<router.NY): continue
            loc=row*router.NX+col
            if via_blocked[loc]: continue
            samples=max(1,math.ceil(math.hypot(vx-x,vy-y)/.05))
            if any(blocked[layer_index*router.SIZE+round((y+(vy-y)*k/samples)/router.STEP)*router.NX+
                           round((x+(vx-x)*k/samples)/router.STEP)] for k in range(samples+1)): continue
            via=pcbnew.PCB_VIA(b);via.SetPosition(V(vx,vy));via.SetWidth(pcbnew.FromMM(.6));via.SetDrill(pcbnew.FromMM(.3))
            via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);via.SetNet(gnd);b.Add(via)
            if math.hypot(vx-x,vy-y)>.01:
                t=pcbnew.PCB_TRACK(b);t.SetStart(V(x,y));t.SetEnd(V(vx,vy));t.SetLayer(layer)
                t.SetWidth(pcbnew.FromMM(.25));t.SetNet(gnd);b.Add(t)
            added.append((vx,vy))
            break
    print('Ground stitching candidates:',len(added),flush=True)
    return len(added)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--board',type=Path,default=OUT/'placed.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'checked.kicad_pcb')
    p.add_argument('--batch',type=int,default=6)
    p.add_argument('--first-net',default='')
    p.add_argument('--fine',action='store_true',help='0.05mm grid, 0.18mm signals, 0.5mm vias within existing rules')
    p.add_argument('--inner-power-crossing',action='store_true',help='Allow IS3 across CH1/2 inner output spreaders; outer power paths remain protected')
    p.add_argument('--compact-crossings',action='store_true',help='Allow remaining compact signals across inner raw pour; front raw bus remains protected')
    a=p.parse_args()
    if a.fine:
        router.STEP=.05
        router.GUARD=.005
        router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
        router.SIZE=router.NX*router.NY
    work=a.output.resolve();candidate=OUT/'checked-candidate.kicad_pcb'
    for target in (work,candidate):
        target.with_suffix('.kicad_pro').write_text(a.board.with_suffix('.kicad_pro').read_text())
    b=pcbnew.LoadBoard(str(a.board));apply_rules(b)
    bounds=b.GetBoardEdgesBoundingBox()
    router.W,router.H=round(pcbnew.ToMM(bounds.GetWidth())),round(pcbnew.ToMM(bounds.GetHeight()))
    router.NX,router.NY=round(router.W/router.STEP)+1,round(router.H/router.STEP)+1
    router.SIZE=router.NX*router.NY
    report=check(b,work)
    assert not errors(report),errors(report)[:3]
    b=pcbnew.LoadBoard(str(work));apply_rules(b)
    if ground_stitch(b,report):
        trial=check(b,candidate)
        if not errors(trial) and len(trial['unconnected_items'])<len(report['unconnected_items']):
            shutil.copyfile(candidate,work);report=trial
        else:
            print('Ground batch rejected',errors(trial)[:2],flush=True)
    b=pcbnew.LoadBoard(str(work));apply_rules(b)
    failed=set();batch=a.batch
    for attempt in range(250):
        pending=[]
        # Short local nets first; route the 24 ESP32 interconnects after the cells.
        def distance(g):
            x,y=[i['pos'] for i in g['items']]
            priority=0 if any(f'[/{a.first_net}]' in i['description'] for i in g['items']) else 1
            return priority,math.hypot(x['x']-y['x'],x['y']-y['y'])
        for gap in sorted(report['unconnected_items'],key=distance):
            key=tuple(sorted(i['uuid'] for i in gap['items']))
            if key in failed: continue
            objects=items_by_id(b)
            if any(i['uuid'] not in objects for i in gap['items']): continue
            one,two=[objects[i['uuid']] for i in gap['items']]
            net=short_name(one)
            if net=='GND': continue
            if net=='BATT_RAW' or net.startswith(('VS','LOAD','USB','VIN','VBUS','LOGIC_FUSED','DGATE','CAP_USB')):
                failed.add(key);print('Power/manual route needs review:',net,flush=True);continue
            print(f'Routing {net}: {len(report["unconnected_items"])} gaps remain',flush=True)
            width,diameter,drill=(.5,.8,.4) if net=='+3V3' else (.2,.6,.3)
            if a.fine and net!='+3V3':width,diameter,drill=.18,.5,.3
            compact=a.compact_crossings and net in ('IS1','DEN1','DEN5','DEN6','UGND2','UGND3')
            blocked,via_blocked=router.obstacles(AliasBoard(b,a.inner_power_crossing and net=='IS3',compact),one.GetNetCode(),width,diameter)
            starts=router.anchors(router.component(b,one),blocked)
            goals=router.anchors(router.component(b,two),blocked)
            if not starts or not goals:
                failed.add(key);print('  no accessible anchor',flush=True);continue
            if starts.keys()&goals.keys(): continue
            path=router.search(blocked,via_blocked,starts,goals)
            if not path:
                failed.add(key);continue
            router.add_route(b,one.GetNet(),path,starts,goals,width,diameter,drill)
            pending.append(key);b.BuildConnectivity()
            if len(pending)>=batch: break
        if not pending: break
        trial=check(b,candidate)
        if errors(trial) or signal_count(trial)>=signal_count(report):
            print('Rejected batch:',errors(trial)[:1],flush=True)
            if len(pending)>1: batch=1
            else: failed.add(pending[0])
        else:
            shutil.copyfile(candidate,work);report=trial;batch=a.batch
            print('Accepted:',len(pending),'routes;',len(report['unconnected_items']),'gaps',flush=True)
        b=pcbnew.LoadBoard(str(work));apply_rules(b)
    # New pours can expose additional ground islands after routing.
    if ground_stitch(b,report):
        trial=check(b,candidate)
        if not errors(trial) and len(trial['unconnected_items'])<len(report['unconnected_items']):
            shutil.copyfile(candidate,work);report=trial
    work.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Remaining:',len(report['unconnected_items']),'gaps;',len(errors(report)),'copper errors',flush=True)


if __name__=='__main__': main()
