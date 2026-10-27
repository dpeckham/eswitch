#!/usr/bin/env python3
"""Generate candidate 14x51 fuse mounting using MR14SPRING clips and M5 terminals.

Run with KiCad Python. Electrical land geometry is copied from the reviewed
74650195 footprint. The 86 mm terminal pitch and 42 mm clip-center spacing
are from Mersen DS-IEC-FUSE-CLIPS-08-0624. Use M5 flat washers spanning the
clips' 6.5 mm mounting holes; dry-fit/alignment and contact heating need testing.
"""
from route_checked import pcbnew, HERE, V


def main():
    library = HERE / 'lib/eswitch.pretty'
    stud = pcbnew.FootprintLoad(str(library), 'ScrewTerminal_Wuerth_74650195_M5')
    if stud is None:
        raise RuntimeError('Missing reviewed M5 terminal footprint')
    name = 'Fuse_Mersen_14x51_MR14_Wuerth_M5'
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('eswitch', name))
    fp.SetReference('REF**')
    fp.SetValue('14x51 + MR14SPRING + 74650195')
    fp.SetLibDescription('CANDIDATE: MR14SPRING clips on 74650195 terminals, 86 mm pitch; M5 washers required')
    for number, x in [('1', -43), ('2', 43)]:
        for p in stud.Pads():
            clone = p.Duplicate()
            clone.SetParent(fp)
            clone.SetNumber(number if p.GetNumber() else '')
            clone.SetPosition(p.GetPosition() + V(x, 0))
            fp.Add(clone)
    for layer, width, height in [(pcbnew.F_Fab, 100, 20.7), (pcbnew.F_CrtYd, 101, 21.7)]:
        rect = pcbnew.PCB_SHAPE(fp)
        rect.SetShape(pcbnew.SHAPE_T_RECT)
        rect.SetLayer(layer)
        rect.SetStart(V(-width/2, -height/2))
        rect.SetEnd(V(width/2, height/2))
        rect.SetWidth(pcbnew.FromMM(.05 if layer == pcbnew.F_CrtYd else .1))
        fp.Add(rect)
    fp.Reference().SetPosition(V(0, -12))
    fp.Value().SetPosition(V(0, 12))
    fp.Value().SetLayer(pcbnew.F_Fab)
    pcbnew.FootprintSave(str(library), fp)
    print(library / (name + '.kicad_mod'))


if __name__ == '__main__':
    main()
