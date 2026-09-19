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
import hashlib
import argparse
import pcbnew
from sexp import parse_one, find, find_all, dump
from gen_pcb import Board, V, apply_rules, read_netlist, NETLIST
from pcb_nets import short_name, sync_metadata
from pcb_io import save_board
from input_stage import REFS, main_power, protection_routes
from fanout_revision_b import repair_fanout
from production_silk import apply_silk

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "out/revb-before-latch.kicad_pcb"
DEST = ROOT / "out/latch-candidate.kicad_pcb"
CUT, EXTRA = 89, 32


def outside_stage(start, end):
    """Clip a signal segment to the outside of the new component/fanout area."""
    ax, ay = start
    dx, dy = end[0] - ax, end[1] - ay
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, ax-50), (dx, 121-ax), (-dy, ay-27.8), (dy, 50-ay)):
        if p == 0:
            if q < 0:
                return [(start, end)]
            continue
        t = q / p
        if p < 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
    if lo > hi:
        return [(start, end)]
    point = lambda t: (round(ax+t*dx, 6), round(ay+t*dy, 6))
    return ([(start, point(lo))] if lo > 0 else []) + ([(point(hi), end)] if hi < 1 else [])


def mm(p):
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


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
                        find(piece,"uuid")[1]=str(uuid.uuid5(uuid.UUID(find(item,"uuid")[1]), repr((start,end))))
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
    # Clear a bounded signal corridor for the new hardware. MCU/channel ends
    # remain; only these low-speed nets may subsequently use guarded gap repair.
    cleared=[]
    for item in result:
        if not isinstance(item, list) or item[0] not in ("segment", "via"):
            cleared.append(item)
            continue
        name=short_name(find(item,"net")[1])
        if not name.startswith(("IN", "IS", "DEN", "UGND", "+3V3")):
            cleared.append(item)
            continue
        if item[0]=="via":
            x,y=map(float,find(item,"at")[1:3])
            if not (50 <= x <= 121 and 27.8 <= y <= 50):
                cleared.append(item)
            continue
        start=tuple(map(float,find(item,"start")[1:3]))
        end=tuple(map(float,find(item,"end")[1:3]))
        pieces=outside_stage(start,end)
        if pieces==[(start,end)]:
            cleared.append(item)
            continue
        for a,b in pieces:
            if a==b:
                continue
            piece=deepcopy(item)
            find(piece,"start")[1:3]=a
            find(piece,"end")[1:3]=b
            find(piece,"uuid")[1]=str(uuid.uuid5(uuid.UUID(find(item,"uuid")[1]),repr((a,b))))
            cleared.append(piece)
    path=ROOT/"out/latch-translated.kicad_pcb"
    path.write_text(dump(cleared)+"\n")
    shutil.copy2(SOURCE.with_suffix(".kicad_pro"),path.with_suffix(".kicad_pro"))
    return path


def main():
    global DEST
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=DEST)
    args=parser.parse_args()
    DEST=args.output.resolve()
    assert DEST != ROOT/"eswitch.kicad_pcb", "Migration writes a review candidate, never the tracked board"
    DEST.parent.mkdir(parents=True,exist_ok=True)
    if not SOURCE.exists():
        original=pcbnew.LoadBoard(str(ROOT/"eswitch.kicad_pcb"))
        assert not any(fp.GetReference()=="U14" for fp in original.GetFootprints())
        assert abs(pcbnew.ToMM(original.GetBoardEdgesBoundingBox().GetWidth())-221)<.1
        shutil.copy2(ROOT/"eswitch.kicad_pcb",SOURCE)
        shutil.copy2(ROOT/"eswitch.kicad_pro",SOURCE.with_suffix(".kicad_pro"))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == (
        "6482993dbfc8724b58c9914ae6316859a5164590e9f5e608c9476d0aa4b7ba22"
    ), "Migration requires the documented 221 mm revision-B source snapshot"
    board=pcbnew.LoadBoard(str(translated_source()))
    retained_nets={}
    apply_rules(board)
    # Geometry/removal happen in serialized form before loading KiCad. Never
    # keep detached SWIG wrappers or mutate live endpoint vectors.
    for track in board.GetTracks():
        retained_nets[track.m_Uuid.AsString()] = track.GetNetname()
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
    detached_fanout = repair_fanout(board)
    bd.text("LOGIC MAX 2A",98.5,50,layer=pcbnew.B_SilkS,size=.8)
    detached_silk = apply_silk(board)
    # Unchanged physical pads retain their connectivity; replaced components are
    # assigned from the NEW netlist by Board.place, not merely metadata-renamed.
    sync_metadata(board,NETLIST)
    # KiCad may infer a via's net from a crossing trace during connectivity
    # building. Assert new copper too: otherwise that accidental reassignment
    # can conceal a crossing from DRC after the next zone refill.
    removed={t.m_Uuid.AsString() for t in detached_fanout}
    for t in board.GetTracks():
        old=retained_nets.get(t.m_Uuid.AsString())
        if old is not None:
            assert short_name(old)==short_name(t), ("before fill",old,t.GetNetname())
        retained_nets[t.m_Uuid.AsString()]=t.GetNetname()
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
    assert {fp.GetReference() for fp in board.GetFootprints()} == set(bd.comps)
    source_doc=parse_one(SOURCE.read_text())
    unchanged=0
    for fp in find_all(source_doc,"footprint"):
        ref=next(p[2] for p in find_all(fp,"property") if p[1]=="Reference")
        if ref in REFS:
            continue
        x,y=map(float,find(fp,"at")[1:3])
        actual=bd.fps[ref]
        # KiCad's decimal parser rounds to nm; FromMM truncates binary floats.
        expected=pcbnew.VECTOR2I(round((x+EXTRA if x>CUT else x)*1e6),round(y*1e6))
        assert (actual.GetPosition()-expected).EuclideanNorm() <= 1, (ref,"position changed")
        assert actual.m_Uuid.AsString()==find(fp,"uuid")[1], (ref,"identity changed")
        unchanged+=1
    save_board(DEST,board)
    shutil.copy2(ROOT/"eswitch.kicad_pro",DEST.with_suffix(".kicad_pro"))
    geometry={ref:[dict(pin=p.GetNumber(),net=p.GetNetname(),xy=mm(p.GetPosition()),
                         size=mm(p.GetSize())) for p in fp.Pads() if p.GetNumber()]
              for ref,fp in bd.fps.items() if ref in REFS}
    DEST.with_suffix(".pads.json").write_text(json.dumps(geometry,indent=2)+"\n")
    # GetSize() references its C++ BOX2I. Keep the parent alive while reading it.
    bounds = board.GetBoardEdgesBoundingBox()
    audit=dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               candidate_sha256=hashlib.sha256(DEST.read_bytes()).hexdigest(),
               unchanged_footprints_verified=unchanged,
               copper_assignments_verified=len(retained_nets)-len(removed),
               board_size_mm=mm(bounds.GetSize()),
               note="Coordinates include the 0.1 mm outline stroke; DRC still required")
    DEST.with_suffix(".migration.json").write_text(json.dumps(audit,indent=2)+"\n")
    print("Candidate saved, existing signal routes preserved. DRC still required.")


if __name__=="__main__":
    main()
