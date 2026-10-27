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
    def __init__(self,b,inner_crossing=False,compact_crossing=False,power_pad_escapes=False,ground_power_escapes=False,local_power_escapes=False,aux_pour_escapes=False):
        self.board=b;self.inner_crossing=inner_crossing;self.compact_crossing=compact_crossing
        self.power_pad_escapes=power_pad_escapes
        self.ground_power_escapes=ground_power_escapes
        self.local_power_escapes=local_power_escapes
        self.aux_pour_escapes=aux_pour_escapes
    def __getattr__(self,k): return getattr(self.board,k)
    def FindNet(self,name): return self.board.FindNet(name) or self.board.FindNet('/'+name)
    def Zones(self):
        return [z for z in self.board.Zones() if not (
            (self.ground_power_escapes and not z.GetIsRuleArea() and short_name(z) in ('AUTO_PROTECTED','BATT_RAW')) or (
            self.local_power_escapes and not z.GetIsRuleArea() and z.GetLayer()==pcbnew.B_Cu and short_name(z)=='AUTO_PROTECTED') or (
            self.aux_pour_escapes and not z.GetIsRuleArea() and short_name(z) in ('VIN','VBUS','AUTO_PROTECTED')) or (
            not z.GetIsRuleArea() and z.GetLayer()==pcbnew.In2_Cu
            and ((self.inner_crossing and short_name(z) in ('LOAD1','LOAD2'))
                 or (self.compact_crossing and short_name(z) in ('BATT_RAW','LOAD1','LOAD2','LOAD5','LOAD6')))))]


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


def isolated_power_stub(board,item):
    """Only a genuinely isolated low-current branch may use signal-size copper.

    An R/C endpoint can belong to a whole power island. Looking at its reference
    alone would incorrectly permit a thin bridge between two high-current buses.
    """
    group=router.component(board,item)
    pads=[p for p in group if p.GetClass()=='PAD']
    if not pads or not all(p.GetParentFootprint().GetReference().startswith(('R','C'))
                           or p.GetParentFootprint().GetReference()=='U15' for p in pads):
        return False
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetCode()!=item.GetNetCode():continue
        for member in group:
            if member.IsOnLayer(z.GetLayer()) and z.GetFilledPolysList(z.GetLayer()).Contains(member.GetPosition()):
                return False
    return True


def ground_stitch(b,report,power_escapes=False):
    """Connect disconnected SMD ground pads locally to In1, with raster clearances."""
    gnd=b.FindNet('/GND') or b.FindNet('GND')
    blocked,via_blocked=router.obstacles(AliasBoard(b,ground_power_escapes=power_escapes),gnd.GetNetCode(),.25,.6)
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
        # PAD.GetLayer() can report the inherited front-layer default even for
        # a rear SMD land. The pad's layer set is the authoritative copper side.
        copper_layers=[layer for layer in router.LAYERS if pad.IsOnLayer(layer)]
        if len(copper_layers)!=1:continue
        layer=copper_layers[0]
        layer_index=router.LAYERS.index(layer)
        offsets=[(0,0)]+[(r*math.cos(a*math.pi/4),r*math.sin(a*math.pi/4)) for r in (.8,1.2,1.6,2,2.4,3.2,4,6,8) for a in range(8)]
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
    p.add_argument('--power-stubs',action='store_true',help='Route low-current R/C/controller branches of reserved power nets; never join power terminals or islands')
    p.add_argument('--power-pad-escapes',action='store_true',help='Allow signal vias within their own pad lands inside power pours; retain physical and rule-area clearances')
    p.add_argument('--aux-supplies',action='store_true',help='Route VIN/VBUS logic supplies and the F9 input branch with 0.8 mm copper and 0.4 mm drills')
    p.add_argument('--aux-width',type=float,default=.8,help='Logic-supply track width; 0.3 mm permits fine-pitch controller escape')
    p.add_argument('--ground-power-escapes',action='store_true',help='Allow local ground stitching through AUTO_PROTECTED pours while preserving explicit power tracks and rule areas')
    p.add_argument('--local-power-escapes',action='store_true',help='Allow PROFET ISP/DENR fanout through rear supply pours; preserve explicit power tracks')
    p.add_argument('--fine',action='store_true',help='0.05mm grid, 0.18mm signals, 0.5mm vias within existing rules')
    p.add_argument('--inner-power-crossing',action='store_true',help='Allow IS3 across CH1/2 inner output spreaders; outer power paths remain protected')
    p.add_argument('--compact-crossings',action='store_true',help='Allow remaining compact signals across inner raw pour; front raw bus remains protected')
    a=p.parse_args()
    if a.aux_width<.3:raise ValueError('Auxiliary supply width must be at least 0.3 mm')
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
    if ground_stitch(b,report,a.ground_power_escapes):
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
            power=net in ('BATT_RAW','AUTO_FUSED','AUTO_PROTECTED','PROTECTION_COMMON_SOURCE','TVS_INPUT_MID') or net.startswith(('PROFET_OUT','LOAD','USB','VIN','VBUS','LOGIC_FUSED','DGATE_USB','CAP_USB')) or (net.startswith('VS') and net!='VS_CONTROLLER')
            low_current_stub=power and a.power_stubs and net not in ('BATT_RAW','VBUS','VIN','LOGIC_FUSED') and not net.startswith(('LOAD','USB','DGATE_USB','CAP_USB')) and any(
                isolated_power_stub(b,item) for item in (one,two))
            aux_supply=a.aux_supplies and (net in ('VIN','VBUS','DGATE_USB','CAP_USB') or (net=='AUTO_PROTECTED' and any(
                item.GetClass()=='PAD' and item.GetParentFootprint().GetReference()=='F9' for item in (one,two))))
            if power and not low_current_stub and not aux_supply:
                failed.add(key);print('Power/manual route needs review:',net,flush=True);continue
            print(f'Routing {net}: {len(report["unconnected_items"])} gaps remain',flush=True)
            width,diameter,drill=(.5,.8,.4) if net=='+3V3' else (.2,.6,.3)
            if low_current_stub: width=.5
            if a.fine and net!='+3V3':width,diameter,drill=.18,.5,.3
            if aux_supply:width,diameter,drill=a.aux_width,(.6 if a.aux_width<.8 else .8),(.3 if a.aux_width<.8 else .4)
            usb_enable=aux_supply and net=='VBUS' and any(
                item.GetClass()=='PAD' and item.GetParentFootprint().GetReference()=='U13'
                and item.GetNumber()=='6' for item in (one,two))
            if usb_enable:width,diameter,drill=.18,.5,.3
            compact=a.compact_crossings and net in ('IS1','DEN1','DEN5','DEN6','UGND2','UGND3')
            local=a.local_power_escapes and (net.startswith(('ISP','DENR')) or aux_supply)
            blocked,via_blocked=router.obstacles(AliasBoard(b,a.inner_power_crossing and net=='IS3',compact,a.power_pad_escapes,local_power_escapes=local,aux_pour_escapes=aux_supply),one.GetNetCode(),width,diameter)
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
    if ground_stitch(b,report,a.ground_power_escapes):
        trial=check(b,candidate)
        if not errors(trial) and len(trial['unconnected_items'])<len(report['unconnected_items']):
            shutil.copyfile(candidate,work);report=trial
    work.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Remaining:',len(report['unconnected_items']),'gaps;',len(errors(report)),'copper errors',flush=True)


if __name__=='__main__': main()
