#!/usr/bin/env python3
"""Create a plotting-only copy with legible references and hidden values."""
from route_checked import *

b=pcbnew.LoadBoard(str(HERE/'eswitch-simple.kicad_pcb'))
for fp in b.GetFootprints():
    fp.Value().SetVisible(False)
    for item in fp.GraphicalItems():
        if item.GetClass()=='PCB_TEXT':item.SetLayer(pcbnew.Cmts_User)
    ref=fp.Reference()
    ref.SetVisible(True)
    ref.SetLayer(pcbnew.B_Fab if fp.GetLayer()==pcbnew.B_Cu else pcbnew.F_Fab)
    ref.SetPosition(fp.GetPosition());ref.SetTextAngle(pcbnew.EDA_ANGLE(0,pcbnew.DEGREES_T))
    ref.SetTextSize(V(.65,.65));ref.SetTextThickness(pcbnew.FromMM(.1))
    ref.SetMirrored(fp.GetLayer()==pcbnew.B_Cu)
save_board(OUT/'assembly-only.kicad_pcb',b)
