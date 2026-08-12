#!/usr/bin/env python3
import csv
import json
import os
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
BIN = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve() / "Fields2Cover-build/agri_f2c_degree_probe"
OUT = ROOT / "clbos01_degree_bound_42"
OUT.mkdir(exist_ok=True)

ACTIONS = OUT / "actions.csv"
FIELD = OUT / "field_summary.csv"
OVERALL = OUT / "overall_summary.csv"

FRESH_SEL = ROOT / "clbos01_fresh_12_validation/selected_fresh_12_fields.csv"
EXP_SEL = ROOT / "clbos01_expanded_30_validation/selected_expanded_30_fields.csv"
FRESH_ORACLE = ROOT / "clbos01_fresh_12_validation/evaluations.csv"
EXP_ORACLE = ROOT / "clbos01_expanded_30_validation/exhaustive_full_evaluations.csv"

EPS = 1e-6
TOL = 1e-6
TIMEOUT = 900


def read_csv(p):
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append(path, fields, row):
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new: w.writeheader()
        w.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def atomic(path, rows):
    keys, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k); keys.append(k)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def load():
    selected = {}
    for p in [FRESH_SEL, EXP_SEL]:
        for r in read_csv(p):
            selected[r["field_id"]] = r

    oracle = {}
    for p in [FRESH_ORACLE, EXP_ORACLE]:
        for r in read_csv(p):
            status = r.get("status", "SUCCESS")
            err = r.get("error", "")
            key = (r["field_id"], int(r["angle_deg"]))
            if status == "SUCCESS":
                oracle[key] = ("SUCCESS", r)
            elif status == "INFEASIBLE_NO_SWATHS" or (
                status == "FAILED" and "no swaths generated" in err
            ):
                oracle[key] = ("INFEASIBLE_NO_SWATHS", r)
    return selected, oracle


def main():
    if not BIN.exists():
        raise RuntimeError(f"Missing: {BIN}")

    selected, oracle = load()
    fields = [
        "field_id","family","angle_deg","status",
        "swath_total_length_m","mst_total_lb_m",
        "degree_total_lb_m","combined_total_lb_m",
        "mst_le_j","degree_le_j","combined_le_j",
        "mst_le_combined","degree_le_combined",
        "mst_seconds","degree_seconds","combined_probe_total_seconds",
        "oracle_j_m","error",
    ]

    done = {}
    if ACTIONS.exists():
        for r in read_csv(ACTIONS):
            if r["status"] in {"SUCCESS","INFEASIBLE_NO_SWATHS"}:
                done[(r["field_id"], int(r["angle_deg"]))] = r

    ids = sorted(selected)
    total = len(ids)*36
    n = 0
    for fid in ids:
        meta = selected[fid]
        for angle in range(0,180,5):
            n += 1
            key=(fid,angle)
            if key in done:
                print(f"[{n}/{total}] {fid} angle={angle} RESUME_SKIP", flush=True)
                continue

            ostatus, orow = oracle.get(key, ("MISSING", {}))
            try:
                p = subprocess.run(
                    [str(BIN),"--wkt-file",meta["local_wkt_path"],
                     "--angle-deg",str(angle),"--mst-probe"],
                    text=True,capture_output=True,timeout=TIMEOUT,
                )
                if p.returncode == 0:
                    d=json.loads(p.stdout)
                    if ostatus!="SUCCESS":
                        row={"field_id":fid,"family":meta["family"],"angle_deg":angle,
                             "status":"OUTCOME_MISMATCH","error":f"oracle={ostatus}"}
                    else:
                        j=float(orow["complete_path_length_m"])
                        mst=float(d["mst_total_lb_m"])
                        deg=float(d["degree_total_lb_m"])
                        comb=float(d["combined_total_lb_m"])
                        row={
                            "field_id":fid,"family":meta["family"],"angle_deg":angle,
                            "status":"SUCCESS",
                            "swath_total_length_m":d["swath_total_length_m"],
                            "mst_total_lb_m":mst,
                            "degree_total_lb_m":deg,
                            "combined_total_lb_m":comb,
                            "mst_le_j":mst<=j+TOL,
                            "degree_le_j":deg<=j+TOL,
                            "combined_le_j":comb<=j+TOL,
                            "mst_le_combined":mst<=comb+TOL,
                            "degree_le_combined":deg<=comb+TOL,
                            "mst_seconds":d["mst_seconds"],
                            "degree_seconds":d["degree_seconds"],
                            "combined_probe_total_seconds":d["combined_probe_total_seconds"],
                            "oracle_j_m":j,"error":"",
                        }
                else:
                    err=p.stderr.strip()
                    if "no swaths generated" in err and ostatus=="INFEASIBLE_NO_SWATHS":
                        row={"field_id":fid,"family":meta["family"],"angle_deg":angle,
                             "status":"INFEASIBLE_NO_SWATHS","error":""}
                    else:
                        row={"field_id":fid,"family":meta["family"],"angle_deg":angle,
                             "status":"FAILED","error":err}
            except Exception as e:
                row={"field_id":fid,"family":meta["family"],"angle_deg":angle,
                     "status":"DRIVER_ERROR","error":repr(e)}

            append(ACTIONS,fields,row)
            print(f"[{n}/{total}] {fid} angle={angle} {row['status']} {row.get('error','')[:100]}",flush=True)
            if row["status"] in {"SUCCESS","INFEASIBLE_NO_SWATHS"}:
                done[key]=row

    latest={}
    for r in read_csv(ACTIONS):
        if r["status"] in {"SUCCESS","INFEASIBLE_NO_SWATHS"}:
            latest[(r["field_id"],int(r["angle_deg"]))]=r

    fs=[]
    for fid in ids:
        rr=[latest[(fid,a)] for a in range(0,180,5) if (fid,a) in latest]
        if len(rr)!=36:
            fs.append({"field_id":fid,"family":selected[fid]["family"],
                       "status":f"INCOMPLETE_{len(rr)}_OF_36"})
            continue
        feas=[r for r in rr if r["status"]=="SUCCESS"]
        if not feas:
            fs.append({"field_id":fid,"family":selected[fid]["family"],"status":"NO_FEASIBLE"})
            continue

        jstar=min(float(r["oracle_j_m"]) for r in feas)
        c0=sum(float(r["swath_total_length_m"])<jstar+EPS for r in feas)
        cm=sum(float(r["mst_total_lb_m"])<jstar+EPS for r in feas)
        cd=sum(float(r["degree_total_lb_m"])<jstar+EPS for r in feas)
        cc=sum(float(r["combined_total_lb_m"])<jstar+EPS for r in feas)

        fs.append({
            "field_id":fid,"family":selected[fid]["family"],"status":"COMPLETE",
            "feasible_orientation_count":len(feas),
            "all_mst_admissible":all(str(r["mst_le_j"]).lower()=="true" for r in feas),
            "all_degree_admissible":all(str(r["degree_le_j"]).lower()=="true" for r in feas),
            "all_combined_admissible":all(str(r["combined_le_j"]).lower()=="true" for r in feas),
            "c_eps_lsw":c0,"c_eps_mst":cm,"c_eps_degree":cd,"c_eps_combined":cc,
            "combined_saved_vs_mst":cm-cc,
            "combined_full_call_reduction_vs_exhaustive":1-cc/len(feas),
            "median_mst_seconds":statistics.median(float(r["mst_seconds"]) for r in feas),
            "median_degree_seconds":statistics.median(float(r["degree_seconds"]) for r in feas),
        })

    atomic(FIELD,fs)
    comp=[r for r in fs if r["status"]=="COMPLETE"]
    if comp:
        o=[{
            "field_count":len(comp),
            "mst_admissible_fields":sum(str(r["all_mst_admissible"]).lower()=="true" for r in comp),
            "degree_admissible_fields":sum(str(r["all_degree_admissible"]).lower()=="true" for r in comp),
            "combined_admissible_fields":sum(str(r["all_combined_admissible"]).lower()=="true" for r in comp),
            "median_c_lsw":statistics.median(int(r["c_eps_lsw"]) for r in comp),
            "median_c_mst":statistics.median(int(r["c_eps_mst"]) for r in comp),
            "median_c_degree":statistics.median(int(r["c_eps_degree"]) for r in comp),
            "median_c_combined":statistics.median(int(r["c_eps_combined"]) for r in comp),
            "total_c_mst":sum(int(r["c_eps_mst"]) for r in comp),
            "total_c_combined":sum(int(r["c_eps_combined"]) for r in comp),
            "worst_c_mst":max(int(r["c_eps_mst"]) for r in comp),
            "worst_c_combined":max(int(r["c_eps_combined"]) for r in comp),
            "median_degree_to_mst_time_ratio":statistics.median(
                float(r["median_degree_seconds"])/float(r["median_mst_seconds"])
                if float(r["median_mst_seconds"])>0 else 0.0 for r in comp
            ),
        }]
        atomic(OVERALL,o)
    else:
        o=[]

    print("\n=== DEGREE-RELAXATION 42-FIELD RESULT ===")
    for r in fs:
        if r["status"]!="COMPLETE":
            print(r["field_id"],r["status"]); continue
        print(
            f"{r['field_id']}: Ceps "
            f"{r['c_eps_lsw']}->{r['c_eps_mst']} / degree={r['c_eps_degree']} "
            f"-> combined={r['c_eps_combined']} "
            f"saved_vs_mst={r['combined_saved_vs_mst']} "
            f"legal={r['all_combined_admissible']}"
        )
    if o:
        x=o[0]
        print(
            "\nOVERALL "
            f"ADMISSIBLE mst/degree/combined="
            f"{x['mst_admissible_fields']}/{x['degree_admissible_fields']}/{x['combined_admissible_fields']} "
            f"MEDIAN_C={x['median_c_lsw']}->{x['median_c_mst']} "
            f"/ degree={x['median_c_degree']} -> combined={x['median_c_combined']} "
            f"TOTAL_MST_TO_COMBINED={x['total_c_mst']}->{x['total_c_combined']} "
            f"WORST={x['worst_c_mst']}->{x['worst_c_combined']} "
            f"DEGREE_MST_TIME_RATIO={float(x['median_degree_to_mst_time_ratio']):.3f}"
        )
    print("Outputs:",OUT)


if __name__=="__main__":
    main()
