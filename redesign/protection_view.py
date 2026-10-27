#!/usr/bin/env python3
"""Export filled-power polygons for a quick layer-by-layer engineering view."""
from power_geometry import *


def main():
    import json
    b=pcbnew.LoadBoard(str(OUT/'protection-placed.kicad_pcb'))
    nets=['BATT_RAW','AUTO_FUSED','PROTECTION_COMMON_SOURCE','AUTO_PROTECTED',
          *[f'PROFET_OUT{i}' for i in range(1,9)], *[f'LOAD{i}' for i in range(1,9)]]
    data={}
    for layer in (pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu):
        data[b.GetLayerName(layer)]={net:[dict(outer=list(p.exterior.coords),holes=[list(h.coords) for h in p.interiors])
                                         for p in components(copper(b,net,layer)) if p.geom_type=='Polygon'] for net in nets}
    data['labels']=[(f.GetReference(),*router.xy(f.GetPosition())) for f in b.GetFootprints()
                    if f.GetReference().startswith(('F','Q','J')) or f.GetReference() in {f'U{i}' for i in range(1,9)}]
    (OUT/'protection-view.json').write_text(json.dumps(data))


if __name__=='__main__': main()
