#!/usr/bin/env python3
"""Physical local SMD-to-plane connections, with conditional barrel resistance.

Unlike projected planar widths this requires a real pad-layer copper component
and vias in that same local component. Resistance is a full-board-length upper
estimate with assumed 20 um plating, not a thermal/ampacity rating.
"""
from power_geometry import *
from shapely.geometry import box


def analyze_transitions(path):
    b=pcbnew.LoadBoard(str(path));fps={f.GetReference():f for f in b.GetFootprints()}
    cache={}
    def shape(net,layer):
        key=net,layer
        if key not in cache:cache[key]=copper(b,net,layer)
        return cache[key]
    specs=[(f'Q{n}','AUTO_FUSED',pcbnew.In2_Cu,10.,10) for n in range(6,10)]
    specs += [(f'Q{n}','AUTO_PROTECTED',pcbnew.In2_Cu,20.,10) for n in (10,11)]
    specs += [(f'U{n}','AUTO_PROTECTED',pcbnew.In2_Cu,float([10,10,5,5,5,5,5,20][n-1]),12) for n in range(1,9)]
    specs += [(f'U{n}',f'PROFET_OUT{n}',pcbnew.F_Cu,float([10,10,5,5,5,5,5,20][n-1]),6) for n in range(1,9)]
    specs += [('D6','AUTO_FUSED',pcbnew.In2_Cu,0.,1),('D7','GND',pcbnew.In1_Cu,0.,1),
              ('D10','AUTO_PROTECTED',pcbnew.In2_Cu,0.,1),('D10','GND',pcbnew.In1_Cu,0.,1),
              ('F9','AUTO_PROTECTED',pcbnew.In2_Cu,2.,1)]
    rows=[];failures=[]
    for ref,net,target,current,floor in specs:
        pads=[p for p in fps[ref].Pads() if short_name(p)==net]
        layer=next(l for l in (pcbnew.F_Cu,pcbnew.B_Cu) if pads[0].IsOnLayer(l))
        pts=[router.xy(p.GetPosition()) for p in pads]
        # Local window covers the land group and adjacent dedicated transfer bank.
        margin=22 if ref=='D6' else 5
        region=box(min(x for x,y in pts)-margin,min(y for x,y in pts)-margin,
                   max(x for x,y in pts)+margin,max(y for x,y in pts)+margin)
        islands=[s for s in components(shape(net,layer).intersection(region))
                 if any(s.buffer(.002).covers(Point(p)) for p in pts)]
        vias=[]
        for v in b.GetTracks():
            if v.GetClass()!='PCB_VIA' or short_name(v)!=net or not(v.IsOnLayer(layer) and v.IsOnLayer(target)):continue
            xy=router.xy(v.GetPosition());pt=Point(xy)
            if not any(s.covers(pt) for s in islands):continue
            # Require a genuine target-plane connection beyond the via's disk.
            lands=[s for s in components(shape(net,target)) if s.covers(pt)]
            if not any(s.area>2 for s in lands):continue
            vias.append(v)
        area=sum(math.pi*pcbnew.ToMM(v.GetDrillValue())*.020 for v in vias)
        resistance=.01724*.001689/area if area else None
        row=dict(ref=ref,net=net,pad_layer=b.GetLayerName(layer),target_layer=b.GetLayerName(target),
                 connected_local_vias=len(vias),minimum_vias=floor,search_margin_mm=margin,
                 via_uuids=[v.m_Uuid.AsString() for v in vias],
                 drill_mm=[pcbnew.ToMM(v.GetDrillValue()) for v in vias],
                 assumed_plating_mm=.020,assumed_full_length_mm=1.689,
                 parallel_barrel_resistance_20c_mohm=round(resistance*1000,4) if resistance else None,
                 screen_current_a=current,
                 ideal_share_barrel_loss_w=round(current**2*resistance,4) if resistance else None)
        rows.append(row)
        if len(vias)<floor:failures.append(f'{ref} {net}: {len(vias)} local connected vias; minimum {floor}')
    return dict(board_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                status='physical_transition_screen_not_ampacity_qualification',transitions=rows,failures=failures,
                limitations=['Equal via sharing assumed only for resistance calculation; plane spreading/contact resistance excluded',
                             '20 um hole plating is an order requirement, not an as-built measurement',
                             'Counts do not establish neck width from each land to the array or MOSFET sharing',
                             'TVS currents are waveform-dependent and are not assigned DC current ratings'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    r=analyze_transitions(a.board)
    if a.output:a.output.write_text(json.dumps(r,indent=2)+'\n')
    for row in r['transitions']:print(row['ref'],row['net'],row['connected_local_vias'],row['parallel_barrel_resistance_20c_mohm'])
    if r['failures']:raise SystemExit('\n'.join(r['failures']))
