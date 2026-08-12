#!/usr/bin/env python3
import csv, json, math, os, statistics, subprocess, time
from pathlib import Path
from collections import defaultdict

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
CACHE = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve()
MST_BIN = CACHE / "Fields2Cover-build/agri_f2c_mst_probe"
FULL_BIN = CACHE / "Fields2Cover-build/agri_f2c_runner"

BASE = ROOT / "clbos01_external_competitors_1deg_90"
BASE.mkdir(exist_ok=True)

SELECTED = ROOT / "clbos01_heldout_topk/selected_heldout_fields.csv"
BOUND_LOG = BASE / "bound_1deg.csv"
FULL_LOG = BASE / "full_evaluations.csv"
FIELD = BASE / "field_results.csv"
SUMMARY = BASE / "method_summary.csv"
FAMILY = BASE / "family_summary.csv"
SNAPSHOT = BASE / "result_snapshot.txt"

ANGLES = list(range(180))
COARSE = list(range(0, 180, 5))
EPS = 1e-6
TIMEOUT = 900

def read_csv(p):
    if not p.exists() or p.stat().st_size == 0: return []
    with p.open(newline="",encoding="utf-8") as f: return list(csv.DictReader(f))

def append(path, fields, row):
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        if new: w.writeheader()
        w.writerow(row); f.flush(); os.fsync(f.fileno())

def atomic(path, rows):
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)
    os.replace(tmp,path)

def latest(path, ok):
    d={}
    for r in read_csv(path):
        if r["status"] in ok:
            d[(r["field_id"],int(r["angle_deg"]))]=r
    return d

def run_bound(field, angle, done):
    key=(field["field_id"],angle)
    if key in done: return done[key]
    fields=["field_id","family","angle_deg","status","swath_total_length_m",
            "mst_total_lb_m","wall_seconds","error"]
    t0=time.monotonic()
    try:
        p=subprocess.run([str(MST_BIN),"--wkt-file",field["local_wkt_path"],
                          "--angle-deg",str(angle),"--mst-probe"],
                         text=True,capture_output=True,timeout=TIMEOUT)
        wall=time.monotonic()-t0
        if p.returncode==0:
            x=json.loads(p.stdout)
            row={"field_id":field["field_id"],"family":field["family"],
                 "angle_deg":angle,"status":"SUCCESS",
                 "swath_total_length_m":x["swath_total_length_m"],
                 "mst_total_lb_m":x["mst_total_lb_m"],
                 "wall_seconds":f"{wall:.9f}","error":""}
        else:
            err=p.stderr.strip()
            row={"field_id":field["field_id"],"family":field["family"],"angle_deg":angle,
                 "status":"INFEASIBLE_NO_SWATHS" if "no swaths generated" in err else "EXECUTION_FAILURE",
                 "wall_seconds":f"{wall:.9f}","error":err}
    except subprocess.TimeoutExpired:
        row={"field_id":field["field_id"],"family":field["family"],"angle_deg":angle,
             "status":"EXECUTION_FAILURE","wall_seconds":f"{time.monotonic()-t0:.9f}","error":"TIMEOUT"}
    append(BOUND_LOG,fields,row)
    if row["status"] in {"SUCCESS","INFEASIBLE_NO_SWATHS"}: done[key]=row
    return row

def run_full(field, angle, done):
    key=(field["field_id"],angle)
    if key in done: return done[key]
    fields=["field_id","family","angle_deg","status","complete_path_length_m","wall_seconds","error"]
    t0=time.monotonic()
    try:
        p=subprocess.run([str(FULL_BIN),"--wkt-file",field["local_wkt_path"],
                          "--angle-deg",str(angle)],
                         text=True,capture_output=True,timeout=TIMEOUT)
        wall=time.monotonic()-t0
        if p.returncode==0:
            x=json.loads(p.stdout)
            row={"field_id":field["field_id"],"family":field["family"],"angle_deg":angle,
                 "status":"SUCCESS","complete_path_length_m":x["complete_path_length_m"],
                 "wall_seconds":f"{wall:.9f}","error":""}
        else:
            row={"field_id":field["field_id"],"family":field["family"],"angle_deg":angle,
                 "status":"EXECUTION_FAILURE","wall_seconds":f"{wall:.9f}","error":p.stderr.strip()}
    except subprocess.TimeoutExpired:
        row={"field_id":field["field_id"],"family":field["family"],"angle_deg":angle,
             "status":"EXECUTION_FAILURE","wall_seconds":f"{time.monotonic()-t0:.9f}","error":"TIMEOUT"}
    append(FULL_LOG,fields,row)
    if row["status"]=="SUCCESS": done[key]=row
    return row

def circular_fine_neighborhood(center):
    # Matched adaptation of a 5掳 coarse -> 1掳 local refinement:
    # one coarse-cell radius on each side, with 180掳 orientation periodicity.
    return sorted({(center+d)%180 for d in range(-5,6)})

def main():
    for p in [MST_BIN,FULL_BIN,SELECTED]:
        if not p.exists(): raise RuntimeError(f"Missing: {p}")

    selected=read_csv(SELECTED)
    if len(selected)!=90: raise RuntimeError(f"Expected 90 fields, got {len(selected)}")

    bdone=latest(BOUND_LOG,{"SUCCESS","INFEASIBLE_NO_SWATHS"})
    fdone=latest(FULL_LOG,{"SUCCESS"})

    # 1掳 cheap-bound sweep for a common candidate domain.
    total=90*180; n=0
    for field in selected:
        for a in ANGLES:
            n+=1
            r=run_bound(field,a,bdone)
            if r["status"]=="EXECUTION_FAILURE":
                raise RuntimeError(f"Bound failure {field['field_id']} angle={a}: {r['error']}")
            if n%50==0 or a==179:
                print(f"[BOUND {n}/{total}] {field['field_id']} angle={a} {r['status']}",flush=True)

    results=[]
    for idx,field in enumerate(selected,1):
        fid=field["field_id"]
        feasible=[bdone[(fid,a)] for a in ANGLES if (fid,a) in bdone and bdone[(fid,a)]["status"]=="SUCCESS"]
        if not feasible:
            results.append({"field_id":fid,"family":field["family"],"status":"NO_FEASIBLE"})
            continue

        by_mst=sorted(feasible,key=lambda r:(float(r["mst_total_lb_m"]),int(r["angle_deg"])))
        U=math.inf; best_a=None; exact_calls=0
        for r in by_mst:
            if float(r["mst_total_lb_m"]) >= U + EPS: break
            a=int(r["angle_deg"])
            fr=run_full(field,a,fdone)
            if fr["status"]!="SUCCESS":
                raise RuntimeError(f"Full failure exact search {fid} angle={a}: {fr['error']}")
            exact_calls+=1
            j=float(fr["complete_path_length_m"])
            if j<U: U=j; best_a=a

        if not math.isfinite(U): raise RuntimeError(f"No incumbent: {fid}")

        # BF + SwathLength on the common 1掳 domain.
        bf=min(feasible,key=lambda r:(float(r["swath_total_length_m"]),int(r["angle_deg"])))
        bf_a=int(bf["angle_deg"])
        bf_full=run_full(field,bf_a,fdone)
        if bf_full["status"]!="SUCCESS": raise RuntimeError(f"BF full failure {fid}")
        bf_j=float(bf_full["complete_path_length_m"])

        # Literature-derived 5掳 coarse -> 1掳 local fine search using the same
        # SwathLength objective to isolate the search schedule.
        coarse_rows=[bdone[(fid,a)] for a in COARSE
                     if (fid,a) in bdone and bdone[(fid,a)]["status"]=="SUCCESS"]
        if not coarse_rows: raise RuntimeError(f"No coarse feasible candidates: {fid}")
        coarse_best=min(coarse_rows,key=lambda r:(float(r["swath_total_length_m"]),int(r["angle_deg"])))
        coarse_a=int(coarse_best["angle_deg"])
        fine_angles=circular_fine_neighborhood(coarse_a)
        fine_rows=[bdone[(fid,a)] for a in fine_angles
                   if (fid,a) in bdone and bdone[(fid,a)]["status"]=="SUCCESS"]
        ctf=min(fine_rows,key=lambda r:(float(r["swath_total_length_m"]),int(r["angle_deg"])))
        ctf_a=int(ctf["angle_deg"])
        ctf_full=run_full(field,ctf_a,fdone)
        if ctf_full["status"]!="SUCCESS": raise RuntimeError(f"C2F full failure {fid}")
        ctf_j=float(ctf_full["complete_path_length_m"])

        # Intended cheap evaluation counts, not the oracle sweep work.
        ctf_unique_cheap=len(set(COARSE).union(fine_angles))

        results.append({
            "field_id":fid,"family":field["family"],"status":"COMPLETE",
            "feasible_orientation_count":len(feasible),
            "oracle_j_star_m":f"{U:.12f}","oracle_best_angle_deg":best_a,
            "mst_certified_full_calls":exact_calls,
            "bf_sl_angle_deg":bf_a,"bf_sl_j_m":f"{bf_j:.12f}",
            "bf_sl_regret":f"{bf_j/U-1:.12f}","bf_sl_exact":bf_j/U-1<=1e-9,
            "bf_sl_cheap_angle_evals":len(feasible),"bf_sl_full_calls":1,
            "ctf_coarse_winner_deg":coarse_a,"ctf_angle_deg":ctf_a,
            "ctf_j_m":f"{ctf_j:.12f}","ctf_regret":f"{ctf_j/U-1:.12f}",
            "ctf_exact":ctf_j/U-1<=1e-9,
            "ctf_cheap_angle_evals":ctf_unique_cheap,"ctf_full_calls":1,
            "ctf_definition":"5deg coarse over 0-175; 1deg refinement within +/-5deg modulo 180; SwathLength objective",
        })
        print(
            f"[FIELD {idx}/90] {fid}: BF exact={results[-1]['bf_sl_exact']} "
            f"C2F exact={results[-1]['ctf_exact']} "
            f"MSTfull={exact_calls} J*={U:.3f}",
            flush=True
        )

    atomic(FIELD,results)
    complete=[r for r in results if r["status"]=="COMPLETE"]

    methods=[]
    for name,prefix in [("BF_SWATHLENGTH_1DEG","bf_sl"),("LIT_DERIVED_C2F_SWATHLENGTH","ctf")]:
        regs=[float(r[f"{prefix}_regret"]) for r in complete]
        exact=sum(str(r[f"{prefix}_exact"]).lower()=="true" for r in complete)
        methods.append({
            "method":name,"field_count":len(complete),
            "exact_count":exact,"exact_rate":exact/len(complete),
            "median_regret":statistics.median(regs),"max_regret":max(regs),
            "nonzero_regret_count":sum(x>1e-12 for x in regs),
            "median_cheap_angle_evals":statistics.median(int(r[f"{prefix}_cheap_angle_evals"]) for r in complete),
            "median_full_calls":statistics.median(int(r[f"{prefix}_full_calls"]) for r in complete),
        })
    methods.append({
        "method":"MST_CERTIFIED_EXACT_1DEG","field_count":len(complete),
        "exact_count":len(complete),"exact_rate":1.0,"median_regret":0.0,"max_regret":0.0,
        "nonzero_regret_count":0,"median_cheap_angle_evals":180,
        "median_full_calls":statistics.median(int(r["mst_certified_full_calls"]) for r in complete),
        "worst_full_calls":max(int(r["mst_certified_full_calls"]) for r in complete),
    })
    atomic(SUMMARY,methods)

    fam=[]
    for family in sorted(set(r["family"] for r in complete)):
        rr=[r for r in complete if r["family"]==family]
        for name,prefix in [("BF_SWATHLENGTH_1DEG","bf_sl"),("LIT_DERIVED_C2F_SWATHLENGTH","ctf")]:
            regs=[float(r[f"{prefix}_regret"]) for r in rr]
            fam.append({"family":family,"method":name,"field_count":len(rr),
                        "exact_count":sum(str(r[f"{prefix}_exact"]).lower()=="true" for r in rr),
                        "max_regret":max(regs)})
    atomic(FAMILY,fam)

    lines=[
        "CLBOS01 EXTERNAL ORIENTATION-SEARCH COMPETITORS 鈥?COMMON 1掳 DOMAIN, 90 FIELDS","",
        "BF+SwathLength: Fields2Cover/Fields2Benchmark domain baseline.",
        "C2F: literature-derived 5掳 coarse -> 1掳 local refinement schedule, matched to SwathLength.",
        "C2F is an adaptation of the published search structure, not a full reproduction of the source paper.",
        "",
    ]
    print("\n=== EXTERNAL COMPETITOR SUMMARY ===")
    for r in methods:
        text=(f"{r['method']}: exact={r['exact_count']}/{r['field_count']} "
              f"({100*r['exact_rate']:.1f}%) max_regret={100*float(r['max_regret']):.4f}% "
              f"median_cheap={r['median_cheap_angle_evals']} "
              f"median_full={r['median_full_calls']}"
              + (f" worst_full={r['worst_full_calls']}" if "worst_full_calls" in r else ""))
        print(text); lines.append(text)
    SNAPSHOT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("Outputs:",BASE)

if __name__=="__main__":
    main()
