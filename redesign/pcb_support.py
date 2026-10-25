"""Shared board primitives for the compact layout generator."""
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'out/redesign'
NETLIST=OUT/'netlist.net'
os.environ.setdefault('KICAD_STOCK_DATA_HOME','/Applications/KiCad/KiCad.app/Contents/SharedSupport')
sys.path.insert(0,str(ROOT/'tools'))
import wx
app=wx.App(False)
import pcbnew
import gen_pcb
from gen_pcb import Board,V
from pcb_nets import sync_metadata
from pcb_io import save_board
from layout_revision_b import logic,buck_routes,usb_routes,usb_power_routes
from fabrication_rules import configure_usb

F,B,I1,I2=pcbnew.F_Cu,pcbnew.B_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu


def hole_keepout(bd,x,y):
    import math
    for layer in (F,I1,I2,B):
        z=pcbnew.ZONE(bd.b)
        z.SetLayer(layer);z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
        z.SetDoNotAllowZoneFills(True);z.SetZoneName('M3 hardware exclusion')
        z.AddPolygon(pcbnew.VECTOR_VECTOR2I([V(x+4*math.cos(t*math.pi/16),y+4*math.sin(t*math.pi/16)) for t in range(32)]))
        bd.b.Add(z)
