#!/usr/bin/env python3
"""Protocol-fixed inventory, family labels, eligibility, and quantile-balanced selection."""
import argparse, csv, hashlib, math, sys
from pathlib import Path
from shapely import wkt
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import transform
from pyproj import CRS, Transformer

ANGLES = (0, 30, 60, 90, 120, 150)
FAMILIES = ("CONVEX_NO_HOLES", "NONCONVEX_NO_HOLES", "HAS_HOLES_OR_INTERNAL_OBSTACLES")

def polygons(g):
    if isinstance(g, Polygon): return [g]
    if isinstance(g, MultiPolygon): return list(g.geoms)
    return []
def family(g):
    ps = polygons(g); holes = sum(len(p.interiors) for p in ps)
    if holes: return FAMILIES[2]
    ratio = g.area / g.convex_hull.area if g.convex_hull.area else 0.0
    return FAMILIES[0] if ratio >= 0.995 else FAMILIES[1]
def local_projector(g):
    c = g.representative_point(); lon, lat = c.x, c.y
    if not (-180 <= lon <= 180 and -90 <= lat <= 90): raise ValueError("WKT is not longitude/latitude EPSG:4326")
    zone = int((lon + 180) // 6) + 1; epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return Transformer.from_crs("EPSG:4326", CRS.from_epsg(epsg), always_xy=True), f"EPSG:{epsg}"
def has_swaths_after_headland(g):
    core = g.buffer(-6.0)
    if core.is_empty or core.area <= 0: return False
    # A deterministic geometry-only eligibility test; it neither uses nor chooses a planner.
    usable = 0
    for angle in ANGLES:
        rad = math.radians(angle); dx, dy = math.cos(rad), math.sin(rad)
        minx, miny, maxx, maxy = core.bounds; span = math.hypot(maxx-minx, maxy-miny) + 20
        for offset in range(-int(span), int(span) + 1, 2):
            cx, cy = core.centroid.x - dy*offset, core.centroid.y + dx*offset
            from shapely.geometry import LineString
            if not core.intersection(LineString([(cx-dx*span, cy-dy*span),(cx+dx*span, cy+dy*span)])).is_empty:
                usable += 1; break
    return usable >= 4
def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
def main():
    a=argparse.ArgumentParser(); a.add_argument("--dataset", required=True); a.add_argument("--canary", required=True); a.add_argument("--work", required=True); args=a.parse_args()
    ds, out, work=Path(args.dataset), Path(args.canary), Path(args.work); out.mkdir(parents=True, exist_ok=True); work.mkdir(parents=True, exist_ok=True)
    inventory=[]; exclusions=[]
    for path in sorted(ds.rglob("*.wkt")):
        raw=path.read_text(encoding="utf-8").strip(); sha=hashlib.sha256(raw.encode()).hexdigest()
        try:
            geo=wkt.loads(raw)
            if not isinstance(geo, Polygon): raise ValueError("WKT is not one field polygon")
            tfm, crs=local_projector(geo); metric=transform(tfm.transform, geo)
            if not metric.is_valid or metric.area <= 0: raise ValueError("invalid or non-positive metric polygon")
            fam=family(metric)
            if not has_swaths_after_headland(metric): raise ValueError("no valid 6m-headland working area")
        except Exception as e:
            exclusions.append({"source_path":str(path.relative_to(ds)),"reason":str(e),"source_wkt_sha256":sha}); continue
        inventory.append({"source_path":str(path.relative_to(ds)),"family":fam,"area_m2":f"{metric.area:.6f}","source_wkt_sha256":sha,"projection_or_local_transform":crs,"decomposition_algorithm":"TRAPEZOIDAL_SPLIT_0_DEG"})
        (work / (sha+".wkt")).write_text(metric.wkt, encoding="utf-8")
    write_csv(out/"field_inventory.csv", inventory, list(inventory[0]) if inventory else ["source_path","family","area_m2","source_wkt_sha256","projection_or_local_transform","decomposition_algorithm"])
    write_csv(out/"field_exclusions.csv", exclusions, ["source_path","reason","source_wkt_sha256"])
    selected=[]
    for fam in FAMILIES:
        candidates=sorted((x for x in inventory if x["family"]==fam),key=lambda x:float(x["area_m2"]))
        if len(candidates)<4: raise RuntimeError(f"{fam} has fewer than four eligible public fields")
        indices=[round(i*(len(candidates)-1)/3) for i in range(4)]
        for n, ix in enumerate(indices, 1):
            row=dict(candidates[ix]); row["field_id"]=f"{fam}_{n:02d}"; row["local_wkt_path"]=str((work/(row["source_wkt_sha256"]+".wkt")).resolve()); selected.append(row)
    fields=["field_id","family","area_m2","source_path","source_wkt_sha256","projection_or_local_transform","decomposition_algorithm","local_wkt_path"]
    write_csv(out/"selected_fields.csv", selected, fields)
    if len(selected)!=12 or {x["family"] for x in selected} != set(FAMILIES): raise RuntimeError("frozen 12-field protocol selection failed")
    print("Selected 12 fields: 4 per frozen family")
if __name__=="__main__":
    try: main()
    except Exception as e: print(f"FIELD_PREPARATION_ERROR: {e}", file=sys.stderr); raise
