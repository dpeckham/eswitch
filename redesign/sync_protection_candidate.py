#!/usr/bin/env python3
"""Refresh value/MPN fields without modifying routed copper or NC metadata."""
from route_checked import *
import circuit


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=OUT/'protection-bom-sync.kicad_pcb')
    p.add_argument('--output',type=Path,default=OUT/'protection-reviewed.kicad_pcb');a=p.parse_args()
    b=pcbnew.LoadBoard(str(a.source));parts={p.ref:p for p in circuit.build()}
    b.GetTitleBlock().SetRevision('PROTO-PWR3')
    b.GetTitleBlock().SetDate('2026-10-27')
    retired=[]
    for item in list(b.GetDrawings()):
        if item.GetClass()=='PCB_DIM_ALIGNED':b.Remove(item);retired.append(item)
    for start,end in (((0,116),(212,116)),((212,116),(212,0))):
        dim=pcbnew.PCB_DIM_ALIGNED(b);dim.SetLayer(pcbnew.Dwgs_User)
        dim.SetStart(V(*start));dim.SetEnd(V(*end));dim.SetHeight(pcbnew.FromMM(6))
        dim.SetUnitsMode(pcbnew.DIM_UNITS_MODE_MM);dim.SetUnitsFormat(pcbnew.DIM_UNITS_FORMAT_BARE_SUFFIX)
        dim.SetPrecision(1);dim.SetTextSize(V(1.5,1.5));dim.SetLineThickness(pcbnew.FromMM(.15));dim.Update();b.Add(dim)
    for f in b.GetFootprints():
        if f.GetReference() not in {'C27','D8','D9',*(f'R{n}04' for n in range(1,9))}:continue
        part=parts[f.GetReference()]
        if f.GetFPID().GetUniStringLibId()!=part.footprint:
            raise ValueError(f'{part.ref}: footprint change requires layout review')
        f.SetValue(part.value)
        for name,value in part.fields.items():
            f.SetField(name,str(value));f.GetField(name).SetVisible(False)
    a.output.with_suffix('.kicad_pro').write_text(a.source.with_suffix('.kicad_pro').read_text())
    r=check(b,a.output)
    if r['violations'] or r['unconnected_items']:raise RuntimeError('Candidate DRC failed')


if __name__=='__main__':main()
