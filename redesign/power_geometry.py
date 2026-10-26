#!/usr/bin/env python3
"""Connected, per-layer copper-width screen, not an ampacity/thermal solver.

Uses saved fills, tracks and pads. Drill/barrel resistance is not modeled; pad
landings are solid in this planar screen. Terminal landing regions (3 mm radius,
8 mm for the battery studs) are exempt from erosion and reported explicitly.
No current-sharing credit is inferred from the existence of multiple layers.
"""
from route_checked import *
import hashlib
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)


def polygons(polyset):
    def points(o): return [router.xy(o.CPoint(j)) for j in range(o.PointCount())]
    return [Polygon(points(polyset.COutline(i)),
                    [points(polyset.CHole(i,h)) for h in range(polyset.HoleCount(i))]).buffer(0)
            for i in range(polyset.OutlineCount())]


def copper(board, net, layer):
    shapes = []
    for z in board.Zones():
        if not z.GetIsRuleArea() and short_name(z)==net and z.GetLayer()==layer:
            shapes.extend(polygons(z.GetFilledPolysList(layer)))
    for f in board.GetFootprints():
        for p in f.Pads():
            if short_name(p)==net and p.IsOnLayer(layer):
                poly=pcbnew.SHAPE_POLY_SET()
                p.TransformShapeToPolygon(poly,layer,0,pcbnew.FromMM(.005),pcbnew.ERROR_INSIDE)
                shapes.extend(polygons(poly))
    for t in board.GetTracks():
        if short_name(t)!=net: continue
        if t.GetClass()=='PCB_VIA':
            shapes.append(Point(router.xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(layer))/2))
        elif t.GetLayer()==layer:
            shapes.append(LineString([router.xy(t.GetStart()),router.xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2))
    return unary_union(shapes).buffer(0)


def components(shape):
    return [shape] if shape.geom_type=='Polygon' else list(shape.geoms)


def neck(shape, start, end, start_radius=3, end_radius=3):
    a,b=Point(start),Point(end)
    if not any(p.buffer(.002).covers(a) and p.buffer(.002).covers(b) for p in components(shape)):
        return None
    terminals=unary_union([a.buffer(start_radius),b.buffer(end_radius)]).intersection(shape)
    def connected(width):
        eroded=shape.buffer(-width/2).union(terminals)
        return any(p.buffer(.002).covers(a) and p.buffer(.002).covers(b) for p in components(eroded))
    lo,hi=0.,30.
    for _ in range(12):
        mid=(lo+hi)/2
        if connected(mid): lo=mid
        else: hi=mid
    return round(lo,2)


def analyze(path):
    board=pcbnew.LoadBoard(str(path)); fps={f.GetReference():f for f in board.GetFootprints()}
    def pad(ref,net):
        pads=[p for p in fps[ref].Pads() if short_name(p)==net]
        positions=[router.xy(p.GetPosition()) for p in pads]
        center=tuple(sum(p[axis] for p in positions)/len(positions) for axis in (0,1))
        # The output-pin centroid is the NC pin 11, not a load terminal.
        if ref.startswith('U') and net.startswith('LOAD'):
            return min(positions,key=lambda p:math.hypot(p[0]-center[0],p[1]-center[1]))
        return center
    cache={}
    def shape(net,layer):
        key=net,layer
        if key not in cache: cache[key]=copper(board,net,layer)
        return cache[key]
    paths=[]
    paths.append(dict(net='BATT_RAW',source='J2',target='central_bus',
                      target_xy_mm=[100,58],landing_exempt_radius_mm=[8,3],
                      connected_width_mm={board.GetLayerName(l):neck(shape('BATT_RAW',l),pad('J2','BATT_RAW'),(100,58),8,3) for l in LAYERS}))
    for n in range(1,9):
        for net,source,target,sr,er in [('BATT_RAW','J2',f'F{n}',8,3),
                                      (f'LOAD{n}',f'F{n}',f'J{n+10}',3,3),
                                      (f'LOAD{n}',f'U{n}',f'J{n+10}',3,3),
                                      (f'VS{n}',f'F{n}',f'U{n}',3,3),
                                      ('GND','J3',f'J{n+10}',8,3)]:
            paths.append(dict(net=net,source=source,target=target,
                landing_exempt_radius_mm=[sr,er],
                connected_width_mm={board.GetLayerName(l):neck(shape(net,l),pad(source,net),pad(target,net),sr,er) for l in LAYERS}))
    thermal=[]
    for n in range(1,9):
        center=router.xy(fps[f'U{n}'].GetPosition())
        vias=[t for t in board.GetTracks() if t.GetClass()=='PCB_VIA' and short_name(t)==f'VS{n}'
              and abs(router.xy(t.GetPosition())[0]-center[0])<1.325
              and abs(router.xy(t.GetPosition())[1]-center[1])<2]
        thermal.append(dict(channel=n,exposed_pad_vias=len(vias),
                            vs_planar_copper_mm2={board.GetLayerName(l):round(shape(f'VS{n}',l).area,2) for l in LAYERS}))
    return dict(board_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                method='Per-layer morphological erosion between same-net pad-group centroids; null means no same-layer path; terminal landings exempt',
                layer_names={key:board.GetLayerName(layer) for key,layer in
                             [('front',pcbnew.F_Cu),('ground',pcbnew.In1_Cu),('inner2',pcbnew.In2_Cu),('back',pcbnew.B_Cu)]},
                limitations=['Not an ampacity, resistance or thermal solution',
                             'Does not establish via-barrel capacity or layer current sharing',
                             'Pads modeled solid; drilled-hole/contact constrictions require separate assessment',
                             'Widest surviving path does not measure parallel paths or neck length'],paths=paths,thermal_geometry=thermal)


def geometry_checks(report):
    """Regression floors for this rework, explicitly not electrical ratings."""
    failures=[];names=report['layer_names']
    if len(report['paths'])!=41 or len(report['thermal_geometry'])!=8:
        failures.append('Incomplete power-path/thermal-geometry report')
    for row in report['paths']:
        if row['target']=='central_bus': required={'front':8.,'inner2':8.}
        elif row['net']=='BATT_RAW': required={'front':4.,'inner2':4.}
        elif row['net'].startswith('LOAD'): required={'front':2.5,'inner2':2.5,'back':2.5}
        elif row['net']=='GND': required={'front':3.,'ground':5.,'back':3.}
        else: required={'front':1.,'inner2':1.,'back':1.}
        for layer,floor in required.items():
            width=row['connected_width_mm'][names[layer]]
            if width is None or width<floor:
                failures.append(f"{row['net']} {row['source']}->{row['target']} {layer}: {width} mm; floor {floor} mm")
    for item in report['thermal_geometry']:
        if item['exposed_pad_vias']<12: failures.append(f"CH{item['channel']}: fewer than 12 EP vias")
    return failures


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('board',type=Path); p.add_argument('--output',type=Path)
    p.add_argument('--plot',type=Path)
    p.add_argument('--check',action='store_true')
    a=p.parse_args()
    if a.plot:
        b=pcbnew.LoadBoard(str(a.board)); pieces=[]
        for layer in (pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu):
            pieces.append(f'<g transform="translate({LAYERS.index(layer)*180},0)">')
            for net,color in [('GND','#bbbbbb'),('BATT_RAW','#e04040')]+[(f'VS{n}','#ddaa00') for n in range(1,9)]+[(f'LOAD{n}','#4080ff') for n in range(1,9)]:
                pieces.append(copper(b,net,layer).svg(scale_factor=.03,fill_color=color))
            pieces.append('</g>')
        a.plot.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 116" width="3600" height="580">'+''.join(pieces)+'</svg>')
        raise SystemExit(0)
    result=analyze(a.board)
    result['geometric_regression_failures']=geometry_checks(result)
    if a.output: a.output.write_text(json.dumps(result,indent=2)+'\n')
    for row in result['paths']: print(row['net'],row['source'],row['target'],row['connected_width_mm'],flush=True)
    if a.check and result['geometric_regression_failures']:
        raise SystemExit('\n'.join(result['geometric_regression_failures']))
