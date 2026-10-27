#!/usr/bin/env python3
"""Candidate power-layer transfer arrays; native DRC remains authoritative."""
from route_checked import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=OUT/'protection-signals5.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-transfers.kicad_pcb')
    a=p.parse_args();b=pcbnew.LoadBoard(str(a.source));apply_rules(b)
    def via(net,x,y):
        v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(pcbnew.FromMM(.8));v.SetDrill(pcbnew.FromMM(.4))
        v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(b.FindNet('/'+net));b.Add(v)
    def outline(z,points):
        z.Outline().RemoveAllContours()
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(x,y) for x,y in points]))
    def zone(net,points,priority,layer=pcbnew.F_Cu):
        z=pcbnew.ZONE(b);z.SetLayer(layer);z.SetNet(b.FindNet('/'+net))
        z.SetAssignedPriority(priority);z.SetLocalClearance(pcbnew.FromMM(.25))
        z.SetMinThickness(pcbnew.FromMM(.25));z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        outline(z,points);z.SetZoneName('power_transfer_'+net);b.Add(z)
    for n in range(1,9):
        cx=108+26*((n-1)%4)
        def xy(x,y):return (cx-x,116-y) if n>4 else (cx+x,y)
        for z in b.Zones():
            if z.GetLayer()==pcbnew.F_Cu and z.GetZoneName()==f'protected_power_LOAD{n}':
                outline(z,[xy(x,y) for x,y in [(2,10),(13,10),(13,41),(-3,41),(-3,35),(7.5,35),(7.5,18),(2,18)]])
        zone(f'PROFET_OUT{n}',[xy(x,y) for x,y in [(-3,21),(6.5,21),(6.5,34),(2,34),(2,27),(-3,27)]],1100+n)
        for x in (3.8,4.6):
            for y in (29.2,30,32,32.8):via(f'PROFET_OUT{n}',*xy(x,y))
    # F10 reaches the high-voltage drain bank on In2; these arrays transfer to
    # its front drain spreader. Current sharing/temperature need separate review.
    for y in (35,51,67,83):
        for dx in (0,1.2,2.4):
            for dy in (-2,-.8,.8,2):via('AUTO_FUSED',33.8+dx,y+dy)
    for ref,x,y in [('Q10',28.675,100),('Q11',50.675,108)]:
        for layer in (pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu):
            zone('AUTO_PROTECTED',[(x-1.5,y-3),(x+5,y-3),(x+5,y+3),(x-1.5,y+3)],1150 if ref=='Q10' else 1151,layer)
        for dx in (-.8,0,.8):
            for dy in (-2,-1.2,1.2,2):via('AUTO_PROTECTED',x+dx,y+dy)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output)
    print('Violations:',len(r['violations']),'gaps:',len(r['unconnected_items']))


if __name__=='__main__':main()
