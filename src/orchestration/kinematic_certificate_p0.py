#!/usr/bin/env python3
import csv, json, math, os, statistics, subprocess, time
from pathlib import Path

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
CACHE = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve()
KIN_BIN = CACHE/"Fields2Cover-build/agri_f2c_kinematic_probe"
NC_BIN = CACHE/"Fields2Cover-build/agri_f2c_runner_nocache"

SELECTED = ROOT/"clbos01_heldout_topk/selected_heldout_fields.csv"
E_BOUND = ROOT/"clbos01_external_competitors_1deg_90/bound_1deg.csv"

BASE = ROOT/"clbos01_kinematic_certificate_p0"
BASE.mkdir(exist_ok=True)
KIN_LOG = BASE/"kinematic_actions.csv"
FULL_LOG = BASE/"nocache_full_actions.csv"
FIELD_OUT = BASE/"field_summary.csv"
SNAPSHOT = BASE/"snapshot.txt"

EPS=1e-6
TIMEOUT=900

HARD = [
    "HOLD_CONVEX_NO_HOLES_02",
    "HOLD_CONVEX_NO_HOLES_15",
    "HOLD_CONVEX_NO_HOLES_29",
    "HOLD_CONVEX_NO_HOLES_27",
    "HOLD_HAS_HOLES_OR_INTERNAL_OBSTACLES_15",
    "HOLD_NONCONVEX_NO_HOLES_14",
]
EASY = [
    "HOLD_CONVEX_NO_HOLES_05",
    "HOLD_NONCONVEX_NO_HOLES_01",
    "HOLD_HAS_HOLES_OR_INTERNAL_OBSTACLES_16",
]
TARGETS=HARD+EASY

def read_csv(p):
    if not p.exists() or p.stat().st_size==0: return []
    with p.open(newline="",encoding="utf-8") as f: return list(csv.DictReader(f))

def append(path, fields, row):
    new=not path.exists() or path.stat().st_size==0
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

def run_json(cmd):
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=TIMEOUT)
    if p.returncode!=0:
        raise RuntimeError(p.stderr.strip())
    return json.loads(p.stdout)

def load_done(path):
    d={}
    for r in read_csv(path):
        if r.get("status")=="SUCCESS":
            d[(r["field_id"],int(r["angle_deg"]))]=r
    return d

def kin(field,a,done):
    key=(field["field_id"],a)
    if key in done: return done[key]
    fs=["field_id","family","angle_deg","status","swath_total_length_m",
        "mst_total_lb_m","kinematic_mst_total_lb_m","upstream_seconds",
        "euclidean_mst_seconds","kinematic_mst_seconds",
        "kinematic_probe_total_seconds","wall_seconds","error"]
    t=time.monotonic()
    try:
        d=run_json([str(KIN_BIN),"--wkt-file",field["local_wkt_path"],
                    "--angle-deg",str(a),"--kinematic-probe"])
        row={"field_id":field["field_id"],"family":field["family"],"angle_deg":a,
             "status":"SUCCESS","swath_total_length_m":d["swath_total_length_m"],
             "mst_total_lb_m":d["mst_total_lb_m"],
             "kinematic_mst_total_lb_m":d["kinematic_mst_total_lb_m"],
             "upstream_seconds":d["upstream_seconds"],
             "euclidean_mst_seconds":d["euclidean_mst_seconds"],
             "kinematic_mst_seconds":d["kinematic_mst_seconds"],
             "kinematic_probe_total_seconds":d["kinematic_probe_total_seconds"],
             "wall_seconds":time.monotonic()-t,"error":""}
    except Exception as e:
        row={"field_id":field["field_id"],"family":field["family"],"angle_deg":a,
             "status":"FAILED","wall_seconds":time.monotonic()-t,"error":repr(e)}
    append(KIN_LOG,fs,row)
    if row["status"]!="SUCCESS": raise RuntimeError(row["error"])
    done[key]=row
    return row

def full(field,a,done):
    key=(field["field_id"],a)
    if key in done: return done[key],False
    fs=["field_id","family","angle_deg","status","complete_path_length_m",
        "wall_seconds","error"]
    t=time.monotonic()
    try:
        d=run_json([str(NC_BIN),"--wkt-file",field["local_wkt_path"],
                    "--angle-deg",str(a)])
        row={"field_id":field["field_id"],"family":field["family"],"angle_deg":a,
             "status":"SUCCESS","complete_path_length_m":d["complete_path_length_m"],
             "wall_seconds":time.monotonic()-t,"error":""}
    except Exception as e:
        row={"field_id":field["field_id"],"family":field["family"],"angle_deg":a,
             "status":"FAILED","wall_seconds":time.monotonic()-t,"error":repr(e)}
    append(FULL_LOG,fs,row)
    if row["status"]!="SUCCESS": raise RuntimeError(row["error"])
    done[key]=row
    return row,True

def main():
    for p in [KIN_BIN,NC_BIN,SELECTED,E_BOUND]:
        if not p.exists(): raise RuntimeError(f"Missing {p}")

    fields={r["field_id"]:r for r in read_csv(SELECTED)}
    for fid in TARGETS:
        if fid not in fields: raise RuntimeError(f"Missing field {fid}")

    eb={}
    for r in read_csv(E_BOUND):
        if r["status"]=="SUCCESS" and r["field_id"] in TARGETS:
            eb[(r["field_id"],int(r["angle_deg"]))]=float(r["mst_total_lb_m"])

    kd=load_done(KIN_LOG)
    fd=load_done(FULL_LOG)
    out=[]

    for idx,fid in enumerate(TARGETS,1):
        field=fields[fid]
        e_rows=[(a,eb[(fid,a)]) for a in range(180) if (fid,a) in eb]
        if not e_rows: raise RuntimeError(f"No E bounds for {fid}")
        e_rows.sort(key=lambda x:(x[1],x[0]))

        init_a=e_rows[0][0]
        fr,_=full(field,init_a,fd)
        U=float(fr["complete_path_length_m"])
        best_a=init_a
        initial_U=U

        e_initial_survivors=[(a,e) for a,e in e_rows if e < initial_U + EPS]
        d_rows=[]
        dominance_ok=True
        for j,(a,e) in enumerate(e_initial_survivors,1):
            kr=kin(field,a,kd)
            d=float(kr["kinematic_mst_total_lb_m"])
            if d + 1e-8 < e: dominance_ok=False
            d_rows.append((a,e,d))
            if j%20==0:
                print(f"[{idx}/9] {fid} kinematic {j}/{len(e_initial_survivors)}",flush=True)

        d_rows.sort(key=lambda x:(x[2],x[0]))

        evaluated_angles={init_a}
        admiss_checked=0
        admiss_ok=True
        for a,e,d in d_rows:
            if d >= U + EPS:
                break
            if a in evaluated_angles:
                fj=float(fd[(fid,a)]["complete_path_length_m"])
                admiss_checked+=1
                if d > fj + 1e-6: admiss_ok=False
                continue
            fr,_=full(field,a,fd)
            evaluated_angles.add(a)
            fj=float(fr["complete_path_length_m"])
            admiss_checked+=1
            if d > fj + 1e-6: admiss_ok=False
            if fj < U:
                U=fj; best_a=a

        jstar=U
        C_E=sum(1 for a,e in e_rows if e < jstar + EPS)
        dmap={a:d for a,e,d in d_rows}
        C_D=sum(1 for a,e in e_rows
                if e < initial_U + EPS and dmap[a] < jstar + EPS)

        kin_times=[float(kd[(fid,a)]["kinematic_mst_seconds"])
                   for a,e in e_initial_survivors]
        kin_total_times=[float(kd[(fid,a)]["kinematic_probe_total_seconds"])
                         for a,e in e_initial_survivors]
        full_times=[float(r["wall_seconds"]) for (ff,a),r in fd.items()
                    if ff==fid and a in evaluated_angles]

        row={
            "field_id":fid,"family":field["family"],
            "class":"HARD" if fid in HARD else "EASY",
            "feasible_count":len(e_rows),
            "initial_angle_deg":init_a,"initial_incumbent_m":initial_U,
            "exact_best_angle_deg":best_a,"nocache_j_star_m":jstar,
            "C_euclidean":C_E,"C_kinematic":C_D,
            "saved_vs_euclidean":C_E-C_D,
            "reduction_vs_euclidean":(C_E-C_D)/C_E if C_E else 0.0,
            "actual_nocache_full_calls":len(evaluated_angles),
            "dominance_E_le_D":dominance_ok,
            "admissibility_checks_on_full_evaluated":admiss_checked,
            "empirical_D_le_J_on_full_evaluated":admiss_ok,
            "kinematic_candidates_computed":len(e_initial_survivors),
            "median_kinematic_mst_seconds":statistics.median(kin_times) if kin_times else 0,
            "median_kinematic_probe_total_seconds":statistics.median(kin_total_times) if kin_total_times else 0,
            "median_nocache_full_wall_seconds":statistics.median(full_times) if full_times else 0,
        }
        out.append(row)
        atomic(FIELD_OUT,out)
        print(
            f"[{idx}/9] {fid}: C_E={C_E} -> C_D={C_D} "
            f"saved={C_E-C_D} ({100*row['reduction_vs_euclidean']:.1f}%) "
            f"Full={len(evaluated_angles)} J*={jstar:.3f} "
            f"nested={dominance_ok} admiss={admiss_ok}",
            flush=True
        )

    hard=[r for r in out if r["class"]=="HARD"]
    CE=sum(int(r["C_euclidean"]) for r in hard)
    CD=sum(int(r["C_kinematic"]) for r in hard)
    red=(CE-CD)/CE if CE else 0.0
    verdict=("STRONG_KEEP" if red>=0.40 else
             "KEEP_IF_COST_OK" if red>=0.25 else
             "MARGINAL" if red>=0.15 else
             "KILL")

    lines=[
        "KINEMATIC CERTIFICATE P0",
        f"HARD_TOTAL_C_E={CE}",
        f"HARD_TOTAL_C_D={CD}",
        f"HARD_REDUCTION={100*red:.2f}%",
        f"VERDICT={verdict}",
        f"ALL_NESTED={all(r['dominance_E_le_D'] for r in out)}",
        f"ALL_EMPIRICAL_ADMISSIBLE_ON_EVALUATED={all(r['empirical_D_le_J_on_full_evaluated'] for r in out)}",
    ]
    SNAPSHOT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("\n=== KINEMATIC CERTIFICATE P0 SUMMARY ===")
    for x in lines: print(x)
    print("Outputs:",BASE)

if __name__=="__main__":
    main()
