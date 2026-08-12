#!/usr/bin/env python3
import csv, json, math, os, platform, statistics, subprocess, time
from pathlib import Path

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
CACHE = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve()
MST_BIN = CACHE / "Fields2Cover-build/agri_f2c_mst_probe"
FULL_BIN = CACHE / "Fields2Cover-build/agri_f2c_runner"
BASE = ROOT / "clbos01_rigorous_runtime"
BASE.mkdir(exist_ok=True)

SELECTED = ROOT / "clbos01_resolution_scaling/selected_scaling_fields.csv"
RUNS = BASE / "runtime_runs.csv"
SUMMARY = BASE / "runtime_summary.csv"
SYSTEM = BASE / "system_snapshot.txt"
SNAPSHOT = BASE / "runtime_snapshot.txt"

TARGET_IDS = [
    "HOLD_CONVEX_NO_HOLES_16",
    "HOLD_NONCONVEX_NO_HOLES_16",
    "HOLD_HAS_HOLES_OR_INTERNAL_OBSTACLES_16",
]
RESOLUTIONS = [("10deg",10.0),("5deg",5.0),("2p5deg",2.5),("1deg",1.0)]
REPEATS = 5
TIMEOUT = 900
EPS = 1e-6

def read_csv(p):
    if not p.exists() or p.stat().st_size == 0:
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def append(path, fields, row):
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new: w.writeheader()
        w.writerow(row); f.flush(); os.fsync(f.fileno())

def atomic(path, rows):
    keys, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k); keys.append(k)
    tmp = path.with_suffix(path.suffix+".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    os.replace(tmp, path)

def angles(step):
    vals=[]; x=0.0
    while x < 180.0-1e-9:
        vals.append(round(x,6)); x += step
    return vals

def run_json(cmd):
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=TIMEOUT)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return json.loads(p.stdout)

def warmup(field):
    run_json([str(MST_BIN),"--wkt-file",field["local_wkt_path"],"--angle-deg","0","--mst-probe"])
    run_json([str(FULL_BIN),"--wkt-file",field["local_wkt_path"],"--angle-deg","0"])

def run_exhaustive(field, aa):
    t0=time.monotonic(); best=math.inf; success=0; infeas=0
    for a in aa:
        try:
            d=run_json([str(FULL_BIN),"--wkt-file",field["local_wkt_path"],"--angle-deg",str(a)])
            success += 1; best=min(best,float(d["complete_path_length_m"]))
        except RuntimeError as e:
            if "no swaths generated" in str(e): infeas += 1
            else: raise
    return dict(wall_seconds=time.monotonic()-t0, full_calls=success,
                feasible_count=success, infeasible_count=infeas, j_star_m=best)

def run_hierarchical(field, aa):
    t0=time.monotonic(); br=[]; infeas=0
    for a in aa:
        try:
            d=run_json([str(MST_BIN),"--wkt-file",field["local_wkt_path"],"--angle-deg",str(a),"--mst-probe"])
            br.append((float(d["mst_total_lb_m"]),a))
        except RuntimeError as e:
            if "no swaths generated" in str(e): infeas += 1
            else: raise
    br.sort()
    U=math.inf; calls=0
    for lb,a in br:
        if lb >= U + EPS: break
        d=run_json([str(FULL_BIN),"--wkt-file",field["local_wkt_path"],"--angle-deg",str(a)])
        calls += 1; U=min(U,float(d["complete_path_length_m"]))
    return dict(wall_seconds=time.monotonic()-t0, full_calls=calls,
                feasible_count=len(br), infeasible_count=infeas, j_star_m=U)

def write_system():
    lines=[
        "CLBOS01 RIGOROUS RUNTIME SYSTEM SNAPSHOT","",
        f"platform={platform.platform()}",
        f"python={platform.python_version()}",
        f"processor={platform.processor()}",
        f"cpu_count={os.cpu_count()}",
        f"repeats={REPEATS}",
        "warmup=one MST probe + one Full call per field",
        "method_order=alternated by repeat",
        "parallel_execution=false",
        "timing_scope=end-to-end Python driver wall clock including subprocess overhead",
        "hierarchical=current conservative implementation; selected Full calls recompute upstream",
    ]
    try:
        head=subprocess.check_output(["git","-C",str(CACHE/"Fields2Cover"),"rev-parse","HEAD"],text=True).strip()
        lines.append(f"Fields2Cover_HEAD={head}")
    except Exception:
        lines.append("Fields2Cover_HEAD=UNAVAILABLE")
    SYSTEM.write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    for p in [MST_BIN,FULL_BIN,SELECTED]:
        if not p.exists(): raise RuntimeError(f"Missing: {p}")
    sel={r["field_id"]:r for r in read_csv(SELECTED)}
    targets=[sel[x] for x in TARGET_IDS]
    write_system()

    fields=["field_id","family","resolution","step_deg","candidate_count","repeat",
            "method","order_in_repeat","status","wall_seconds","full_calls",
            "feasible_count","infeasible_count","j_star_m","error"]
    done={(r["field_id"],r["resolution"],int(r["repeat"]),r["method"])
          for r in read_csv(RUNS) if r.get("status")=="SUCCESS"}

    for field in targets:
        print("WARMUP",field["field_id"],flush=True); warmup(field)
        for label,step in RESOLUTIONS:
            aa=angles(step)
            for rep in range(1,REPEATS+1):
                order=["HIERARCHICAL","EXHAUSTIVE"] if rep%2 else ["EXHAUSTIVE","HIERARCHICAL"]
                for idx,method in enumerate(order,1):
                    key=(field["field_id"],label,rep,method)
                    if key in done:
                        print("SKIP",key,flush=True); continue
                    print("RUN",field["field_id"],label,"rep",rep,method,flush=True)
                    try:
                        res=run_hierarchical(field,aa) if method=="HIERARCHICAL" else run_exhaustive(field,aa)
                        row=dict(field_id=field["field_id"],family=field["family"],resolution=label,
                                 step_deg=step,candidate_count=len(aa),repeat=rep,method=method,
                                 order_in_repeat=idx,status="SUCCESS",
                                 wall_seconds=f"{res['wall_seconds']:.9f}",full_calls=res["full_calls"],
                                 feasible_count=res["feasible_count"],infeasible_count=res["infeasible_count"],
                                 j_star_m=f"{res['j_star_m']:.12f}",error="")
                    except Exception as e:
                        row=dict(field_id=field["field_id"],family=field["family"],resolution=label,
                                 step_deg=step,candidate_count=len(aa),repeat=rep,method=method,
                                 order_in_repeat=idx,status="FAILED",error=repr(e))
                    append(RUNS,fields,row)
                    if row["status"]!="SUCCESS": raise RuntimeError(row["error"])
                    done.add(key)

    rows=[r for r in read_csv(RUNS) if r["status"]=="SUCCESS"]
    detail=[]
    for field in targets:
        for label,step in RESOLUTIONS:
            hr=[r for r in rows if r["field_id"]==field["field_id"] and r["resolution"]==label and r["method"]=="HIERARCHICAL"]
            er=[r for r in rows if r["field_id"]==field["field_id"] and r["resolution"]==label and r["method"]=="EXHAUSTIVE"]
            if len(hr)!=REPEATS or len(er)!=REPEATS: continue
            ht=[float(r["wall_seconds"]) for r in hr]; et=[float(r["wall_seconds"]) for r in er]
            hj=[float(r["j_star_m"]) for r in hr]; ej=[float(r["j_star_m"]) for r in er]
            exact=max(abs(a-b) for a in hj for b in ej)<=1e-6
            detail.append(dict(
                field_id=field["field_id"],family=field["family"],resolution=label,
                candidate_count=int(hr[0]["candidate_count"]),repeat_count=REPEATS,
                exact_objective_match_all_repeats=exact,
                median_hierarchical_seconds=statistics.median(ht),
                median_exhaustive_seconds=statistics.median(et),
                runtime_reduction=1-statistics.median(ht)/statistics.median(et),
                speedup=statistics.median(et)/statistics.median(ht),
                median_hierarchical_full_calls=statistics.median(int(r["full_calls"]) for r in hr),
                hierarchical_q1=statistics.quantiles(ht,n=4,method="inclusive")[0],
                hierarchical_q3=statistics.quantiles(ht,n=4,method="inclusive")[2],
                exhaustive_q1=statistics.quantiles(et,n=4,method="inclusive")[0],
                exhaustive_q3=statistics.quantiles(et,n=4,method="inclusive")[2],
            ))

    pooled=[]
    for label,step in RESOLUTIONS:
        rr=[r for r in detail if r["resolution"]==label]
        pooled.append(dict(
            field_id="POOLED_3_FIELDS",family="ALL",resolution=label,
            candidate_count=rr[0]["candidate_count"],repeat_count=REPEATS,
            exact_objective_match_all_repeats=all(r["exact_objective_match_all_repeats"] for r in rr),
            median_hierarchical_seconds=statistics.median(r["median_hierarchical_seconds"] for r in rr),
            median_exhaustive_seconds=statistics.median(r["median_exhaustive_seconds"] for r in rr),
            runtime_reduction=statistics.median(r["runtime_reduction"] for r in rr),
            speedup=statistics.median(r["speedup"] for r in rr),
            median_hierarchical_full_calls=statistics.median(r["median_hierarchical_full_calls"] for r in rr),
        ))
    atomic(SUMMARY,detail+pooled)

    lines=["CLBOS01 RIGOROUS END-TO-END RUNTIME SNAPSHOT","",
           "3 mid-area representative fields; 5 repeats; alternating method order.",""]
    print("\n=== RIGOROUS RUNTIME SUMMARY ===")
    for r in pooled:
        text=(f"{r['resolution']} M={r['candidate_count']}: "
              f"hier={r['median_hierarchical_seconds']:.3f}s "
              f"exhaustive={r['median_exhaustive_seconds']:.3f}s "
              f"reduction={100*r['runtime_reduction']:.2f}% "
              f"speedup={r['speedup']:.2f}x "
              f"medianFull={r['median_hierarchical_full_calls']} "
              f"exactMatch={r['exact_objective_match_all_repeats']}")
        print(text); lines.append(text)
    SNAPSHOT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("Outputs:",BASE)

if __name__=="__main__":
    main()
