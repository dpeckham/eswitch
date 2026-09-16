"""One-time, crash-safe migration of the routed 221 mm revision-B board.

Run from KiCad Python. The first invocation saves a private source snapshot under
out/. Repeated invocations always start from that snapshot, allowing controlled
layout iteration without discarding the existing MCU/channel signal routing.
Writes only out/latch-candidate.kicad_pcb; inspection/DRC precedes promotion.
"""
import json
from pathlib import Path
import shutil
from copy import deepcopy
import uuid
import pcbnew
from sexp import parse_one, find, find_all, dump
from gen_pcb import Board, V, apply_rules, read_netlist, NETLIST
from pcb_nets import short_name, sync_metadata
from pcb_io import save_board
from input_stage import REFS, main_power, protection_routes

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "out/revb-before-latch.kicad_pcb"
DEST = ROOT / "out/latch-candidate.kicad_pcb"
CUT, EXTRA = 89, 32


def mm(p):
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


def shifted(p):
    x,y=mm(p)
    return V(x+EXTRA if x>CUT else x,y)


def translated_source():
    """Transform serialized geometry by value, without SWIG removal ownership.

    All footprint-local geometry stays local. Only board-level positions move.
    Filled zone caches must be discarded before KiCad rebuilds connectivity.
    """
    doc=parse_one(SOURCE.read_text())
    result=[]
    stage_nets={"BATT_RAW","BATT_MID","DGATE_MAIN","HGATE_MAIN","OV_TOP","OV_MAIN","UV_MAIN","CAP_MAIN","SLEW_MAIN","V12F"}
    obsolete=("BATT+","GND IN","UPSTREAM","40A TOTAL","LOGIC MAX")
    def move(point):
        if point is not None and float(point[1])>CUT:
            point[1]=float(point[1])+EXTRA
    for item in doc:
        if not isinstance(item,list):
            result.append(item); continue
        kind=item[0]
        if kind=="footprint":
            ref=next(p[2] for p in find_all(item,"property") if p[1]=="Reference")
            if ref in REFS:
                continue
            move(find(item,"at"))
        elif kind in ("segment","via"):
            name=short_name(find(item,"net")[1])
            pts=[find(item,"at")] if kind=="via" else [find(item,"start"),find(item,"end")]
            coords=[tuple(map(float,p[1:3])) for p in pts]
            if (name in stage_nets or (name=="+12V" and max(x for x,y in coords)<CUT)
                    or (name=="GND" and all(35<x<89 and 27<y<41 for x,y in coords))):
                continue
            if kind=="segment":
                (ax,ay),(bx,by)=coords
                if min(ax,bx)<CUT<max(ax,bx):
                    cy=ay+(by-ay)*(CUT-ax)/(bx-ax)
                    first,last=((CUT,cy),(CUT+EXTRA,cy)) if ax<CUT else ((CUT+EXTRA,cy),(CUT,cy))
                    aa=(ax+EXTRA if ax>CUT else ax,ay)
                    bb=(bx+EXTRA if bx>CUT else bx,by)
                    pieces=[(aa,first),(last,bb)]
                    if cy>=50:
                        pieces.append((first,last))
                    for start,end in pieces:
                        piece=deepcopy(item)
                        find(piece,"start")[1:3]=start
                        find(piece,"end")[1:3]=end
                        find(piece,"uuid")[1]=str(uuid.uuid4())
                        result.append(piece)
                    continue
            for p in pts:
                move(p)
        elif kind=="zone":
            net=find(item,"net")
            if net and short_name(net[1]) in ("BATT_RAW","BATT_MID","+12V"):
                continue
            item=[p for p in item if not(isinstance(p,list) and p[0] in ("filled_polygon","fill_segments"))]
            for poly in find_all(item,"polygon"):
                for point in find_all(find(poly,"pts"),"xy"):
                    move(point)
        elif kind=="gr_text":
            if item[1].startswith(obsolete):
                continue
            move(find(item,"at"))
        elif kind.startswith("gr_"):
            for key in ("start","end","center","mid","at"):
                move(find(item,key))
        result.append(item)
    path=ROOT/"out/latch-translated.kicad_pcb"
    path.write_text(dump(result)+"\n")
    shutil.copy2(SOURCE.with_suffix(".kicad_pro"),path.with_suffix(".kicad_pro"))
    return path


def main():
    if not SOURCE.exists():
        original=pcbnew.LoadBoard(str(ROOT/"eswitch.kicad_pcb"))
        assert not any(fp.GetReference()=="U14" for fp in original.GetFootprints())
        assert abs(pcbnew.ToMM(original.GetBoardEdgesBoundingBox().GetWidth())-221)<.1
        shutil.copy2(ROOT/"eswitch.kicad_pcb",SOURCE)
        shutil.copy2(ROOT/"eswitch.kicad_pro",SOURCE.with_suffix(".kicad_pro"))
    board=pcbnew.LoadBoard(str(translated_source()))
    retained_nets={}
    apply_rules(board)
    # Discard only superseded stage copper. Existing unrelated routed nets stay.
    stage_nets={"BATT_RAW","BATT_MID","DGATE_MAIN","HGATE_MAIN","OV_TOP","OV_MAIN","UV_MAIN","CAP_MAIN","SLEW_MAIN","V12F"}
    # Keep detached SWIG wrappers alive throughout mutation (KiCad 10 ownership).
    tracks = list(board.GetTracks())
    detached = []
    for t in tracks:
        retained_nets[t.m_Uuid.AsString()]=t.GetNetname()
    # Serialized migration above supersedes the former SWIG mutation path.
    for t in []:
        points=[t.GetPosition()] if t.GetClass()=="PCB_VIA" else [t.GetStart(),t.GetEnd()]
        coords=[mm(p) for p in points]
        name=short_name(t)
        remove=(name in stage_nets or
                (name=="+12V" and max(x for x,y in coords)<CUT) or
                (name=="GND" and all(35<x<89 and 27<y<41 for x,y in coords)))
        if remove:
            board.Remove(t)
            detached.append(t)
            continue
        retained_nets[t.m_Uuid.AsString()]=t.GetNetname()
        if t.GetClass()=="PCB_VIA":
            t.SetPosition(shifted(t.GetPosition()))
        else:
            # GetStart/GetEnd expose live C++ vectors, not value copies. Snapshot
            # BOTH endpoints before either setter, otherwise a split shifts an
            # already modified endpoint a second time.
            ax,ay=mm(t.GetStart()); bx,by=mm(t.GetEnd())
            a,b=V(ax,ay),V(bx,by)
            if min(ax,bx)<CUT<max(ax,bx):
                cy=ay+(by-ay)*(CUT-ax)/(bx-ax)
                left,right=V(CUT,cy),V(CUT+EXTRA,cy)
                first,last=(left,right) if ax<CUT else (right,left)
                t.SetStart(shifted(a)); t.SetEnd(first)
                # The new protection stage occupies this strip. Preserve both
                # old route ends; reroute signals around its copper afterward.
                pieces=[(last,shifted(b))]
                if cy>=50:
                    pieces.insert(0,(first,last))
                for start,end in pieces:
                    piece=pcbnew.PCB_TRACK(board)
                    piece.SetStart(start); piece.SetEnd(end)
                    piece.SetLayer(t.GetLayer()); piece.SetWidth(t.GetWidth()); piece.SetNet(t.GetNet())
                    board.Add(piece)
            else:
                t.SetStart(shifted(a)); t.SetEnd(shifted(b))
    for fp in []:
        if fp.GetReference() in REFS:
            board.Remove(fp)
        elif mm(fp.GetPosition())[0]>CUT:
            fp.Move(V(EXTRA,0))
    for zone in []:
        if short_name(zone) in ("BATT_RAW","BATT_MID","+12V"):
            board.Remove(zone)
            continue
        # Only board-level polygons need the inserted strip; footprint keepouts
        # move with their owning footprint.
        poly=zone.Outline()
        for i in range(poly.OutlineCount()):
            chain=poly.Outline(i)
            for j in range(chain.PointCount()):
                chain.SetPoint(j,shifted(chain.CPoint(j)))
    obsolete=("BATT+", "GND IN", "UPSTREAM", "40A TOTAL", "LOGIC MAX")
    for d in []:
        if d.GetClass()=="PCB_TEXT":
            if d.GetText().startswith(obsolete):
                board.Remove(d)
            elif mm(d.GetPosition())[0]>CUT:
                d.Move(V(EXTRA,0))
        elif d.GetClass()=="PCB_SHAPE":
            d.SetStart(shifted(d.GetStart())); d.SetEnd(shifted(d.GetEnd()))
    # Wrap the existing board in the common generator API and add the new nets.
    bd=Board.__new__(Board)
    bd.b=board
    bd.comps,bd.netlist=read_netlist(NETLIST)
    bd.nets={short_name(n):n for n in board.GetNetsByName().values()}
    for name in bd.netlist:
        alias=short_name(name)
        if alias not in bd.nets:
            n=pcbnew.NETINFO_ITEM(board,name); board.Add(n); bd.nets[alias]=n
    bd.pad_net={(ref,pin):short_name(name) for name,nodes in bd.netlist.items() for ref,pin in nodes}
    bd.fps={fp.GetReference():fp for fp in board.GetFootprints()}
    main_power(bd)
    protection_routes(bd,include_vin=False)
    bd.text("LOGIC MAX 2A",91,46.2,layer=pcbnew.B_SilkS,size=.8)
    # Unchanged physical pads retain their connectivity; replaced components are
    # assigned from the NEW netlist by Board.place, not merely metadata-renamed.
    sync_metadata(board,NETLIST)
    def check_retained_nets(stage):
        for t in board.GetTracks():
            old=retained_nets.get(t.m_Uuid.AsString())
            if old is not None:
                assert short_name(old)==short_name(t), (stage,old,t.GetNetname(),mm(t.GetPosition()))
    check_retained_nets("before connectivity")
    # Zone outlines were translated but their cached filled polygons were not.
    # Never let connectivity propagate nets through those obsolete polygons.
    for z in board.Zones():
        z.UnFill()
    board.BuildConnectivity()
    check_retained_nets("after connectivity")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    check_retained_nets("after fill")
    save_board(DEST,board)
    shutil.copy2(ROOT/"eswitch.kicad_pro",DEST.with_suffix(".kicad_pro"))
    geometry={ref:[dict(pin=p.GetNumber(),net=p.GetNetname(),xy=mm(p.GetPosition()),
                         size=mm(p.GetSize())) for p in fp.Pads() if p.GetNumber()]
              for ref,fp in bd.fps.items() if ref in REFS}
    (ROOT/"out/latch-pads.json").write_text(json.dumps(geometry,indent=2)+"\n")
    print("Candidate saved, existing signal routes preserved. DRC still required.")


if __name__=="__main__":
    main()
