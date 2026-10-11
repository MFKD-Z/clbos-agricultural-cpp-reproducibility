#!/usr/bin/env python3
"""CLBOS M2: matched LB0-only versus LB1-MST certified full-E2E timing.

Runs ONLY on an existing verified Fields2Cover/Fields2Benchmark experiment
workspace. This script never changes the C++ planner, past results, or a paper.
No synthetic data may be used for formal results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

TIMEOUT = 900
EPS = 1e-6
TOL = 1e-6
EXPECTED_HEAD = "92b9f2fcf72d26c44202f9d2ab54fbf25ed87426"
METHODS = ("LB0_CERTIFIED", "LB1_MST_CERTIFIED")
FIELDS = ["field_id","family","repeat","method","order_in_repeat","status",
          "wall_seconds","bound_wall_seconds","selected_full_wall_seconds",
          "full_calls","feasible_count","model_infeasible_count","unresolved_count",
          "objective_m","authority_j_m","exact_to_authority","error"]

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()

def rows(path):
    with open(path,"r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def json_call(cmd):
    try:
        proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            text=True,timeout=TIMEOUT,check=False)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("UNRESOLVED_TIMEOUT: "+str(e)) from e
    if proc.returncode:
        reason=(proc.stderr or proc.stdout or "unknown subprocess failure").strip()
        if "no swaths generated" in reason:
            raise ValueError("MODEL_NO_SWATHS: "+reason)
        raise RuntimeError("UNRESOLVED_RUNNER_EXIT: "+reason[:800])
    try:
        output=json.loads(proc.stdout)
    except Exception as e:
        raise RuntimeError("UNRESOLVED_INVALID_JSON: "+proc.stdout[:400]) from e
    if not isinstance(output,dict):
        raise RuntimeError("UNRESOLVED_NOT_JSON_OBJECT")
    return output

def relpath_from_selection(raw, base, repo):
    path=Path(raw)
    if path.is_absolute() and path.exists(): return path
    attempts=[]
    if base:attempts.append(Path(base)/path)
    attempts += [repo/path, repo.parent/path,Path.cwd()/path]
    for p in attempts:
        if p.is_file():return p.resolve()
    raise FileNotFoundError(f"Missing local projected WKT {raw!r}; looked at {attempts}")

def validated_selection(selection,root,repo,smoke):
    data=rows(selection)
    assert len(data)==18, f"Expected exactly 18 original E3 fields, found {len(data)}"
    assert len({x["field_id"] for x in data})==18
    families=defaultdict(int)
    for d in data:
        families[d["family"]]+=1
        d["resolved_wkt"]=str(relpath_from_selection(d["local_wkt_path"],root,repo))
    assert sorted(families.values())==[6,6,6], families
    if smoke:
        chosen={}
        for d in data:
            if d["family"] not in chosen:chosen[d["family"]]=d
        data=list(chosen.values())
    return data

def validate_authority(path, selected):
    reference=defaultdict(set)
    for d in rows(path):
        if d.get("status")=="SUCCESS":
            x=d.get("authority_oracle_j_m")
            if x: reference[d["field_id"]].add(float(x))
    out={}
    for d in selected:
        values=reference[d["field_id"]]
        assert values, f"No archived oracle for {d['field_id']}"
        if max(values)-min(values)>TOL:
            raise ValueError(f"Inconsistent archived oracle for {d['field_id']}")
        out[d["field_id"]]=min(values)
    return out

def warmup(field,mst,full):
    w=field["resolved_wkt"]
    for a in range(180):
        try:
            # Identical, uncounted warm-up for both stage variants and Full.
            json_call([str(mst),"--wkt-file",w,"--angle-deg",str(a),"--swath-only"])
            json_call([str(mst),"--wkt-file",w,"--angle-deg",str(a),"--mst-probe"])
            json_call([str(full),"--wkt-file",w,"--angle-deg",str(a)])
            return a
        except ValueError:
            continue
    raise RuntimeError(f"No feasible warmup orientation for {field['field_id']}")

def evaluate(field, method, mst, full, oracle):
    wall0=time.monotonic()
    bound0=time.monotonic()
    candidates=[]
    no_swaths=0
    for a in range(180):
        flag="--swath-only" if method=="LB0_CERTIFIED" else "--mst-probe"
        try:
            v=json_call([str(mst),"--wkt-file",field["resolved_wkt"],"--angle-deg",str(a),flag])
        except ValueError:
            no_swaths+=1
            continue
        key="swath_total_length_m" if method=="LB0_CERTIFIED" else "mst_total_lb_m"
        lb=float(v[key])
        if not math.isfinite(lb) or lb<=0:raise RuntimeError(f"UNRESOLVED_INVALID_LB at {a}: {lb}")
        candidates.append((lb,a))
    bound_seconds=time.monotonic()-bound0
    candidates.sort(key=lambda x:(x[0],x[1]))
    incumbent=math.inf
    calls=0
    full0=time.monotonic()
    for lb,a in candidates:
        if math.isfinite(incumbent) and lb>=incumbent+EPS:
            break
        # The same downstream executable and double-precision stopping guard.
        v=json_call([str(full),"--wkt-file",field["resolved_wkt"],"--angle-deg",str(a)])
        j=float(v["complete_path_length_m"])
        if not math.isfinite(j) or j<=0:raise RuntimeError("UNRESOLVED_INVALID_COMPLETE_OBJECTIVE")
        incumbent=min(incumbent,j)
        calls+=1
    full_seconds=time.monotonic()-full0
    if not math.isfinite(incumbent):raise RuntimeError("UNRESOLVED_NO_INCUMBENT")
    exact=abs(incumbent-oracle)<=TOL
    return {"status":"SUCCESS" if exact else "OBJECTIVE_MISMATCH",
            "wall_seconds":time.monotonic()-wall0,
            "bound_wall_seconds":bound_seconds,
            "selected_full_wall_seconds":full_seconds,
            "full_calls":calls,"feasible_count":len(candidates),
            "model_infeasible_count":no_swaths,"unresolved_count":0,
            "objective_m":incumbent,"authority_j_m":oracle,
            "exact_to_authority":str(exact).lower(),"error":""}

def append_row(path,record):
    new=not path.exists()
    with path.open("a",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        if new:w.writeheader()
        w.writerow(record)
        f.flush();os.fsync(f.fileno())

def preflight(args):
    repo=args.repo.resolve()
    assert repo.is_dir(),f"Missing repo: {repo}"
    for p in [args.mst_bin,args.full_bin,args.selection,args.authority]:
        assert p.is_file(),f"Missing file: {p}"
    if args.f2c_source:
        a=subprocess.run(["git","-C",str(args.f2c_source),"rev-parse","HEAD"],
                         capture_output=True,text=True,check=True).stdout.strip()
        assert a==EXPECTED_HEAD,f"Fields2Cover revision mismatch: {a} != {EXPECTED_HEAD}"
    selected=validated_selection(args.selection,args.wkt_root,repo,args.smoke)
    authority=validate_authority(args.authority,selected)
    assert all(x>0 for x in authority.values())
    return selected,authority

def run(args):
    if not args.smoke and args.f2c_source is None:
        raise RuntimeError("Formal runs require --f2c-source at pinned revision")
    selected,authority=preflight(args)
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    runsfile=out/("smoke_runs.csv" if args.smoke else "formal_runs.csv")
    manifest=out/("smoke_environment.json" if args.smoke else "formal_environment.json")
    if runsfile.exists() and args.force_new:raise RuntimeError("Refusing to overwrite prior runs")
    old=rows(runsfile) if runsfile.exists() else []
    if len({(r["field_id"],r["repeat"],r["method"]) for r in old})!=len(old):
        raise RuntimeError("Duplicate run keys in existing CSV")
    existing={(r["field_id"],int(r["repeat"]),r["method"]):r for r in old}
    if any(r["status"]!="SUCCESS" for r in old):
        raise RuntimeError("Existing non-success runs require manual resolution, not silent resume")
    repeats=1 if args.smoke else 5
    info={"mode":"SMOKE_NOT_PUBLISHABLE" if args.smoke else "FORMAL_18x5",
          "start_local":time.strftime("%Y-%m-%d %H:%M:%S%z"),
          "fields2cover_head_required":EXPECTED_HEAD,
          "platform":platform.platform(),"python":platform.python_version(),
          "python_version_detail":sys.version,"cpu_count":os.cpu_count(),
          "mst_bin_sha256":sha(args.mst_bin),"full_bin_sha256":sha(args.full_bin),
          "selection_sha256":sha(args.selection),"authority_sha256":sha(args.authority),
          "experiment_script_sha256":sha(Path(__file__)),
          "fields":[x["field_id"] for x in selected],
          "wkt_sha256_by_field":{x["field_id"]:sha(x["resolved_wkt"]) for x in selected},
          "repeats":repeats,
          "angle_count":180,"max_subprocess_seconds":TIMEOUT,"epsilon_m":EPS,
          "full_timing_scope":"bound acquisition+sorting+complete downstream+Python/subprocess overhead",
          "cache_policy":"Recomputes upstream inside every selected Full call; same as E3 original",
          "methods":METHODS}
    if manifest.exists():
        prior=json.loads(manifest.read_text(encoding="utf-8"))
        keys=["fields","mst_bin_sha256","full_bin_sha256","selection_sha256",
              "authority_sha256","experiment_script_sha256","mode","wkt_sha256_by_field"]
        for k in keys:
            if info[k]!=prior[k]:raise RuntimeError(f"Resume provenance mismatch: {k}")
    else:manifest.write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding="utf-8")
    for idx,d in enumerate(selected):
        if not args.smoke and all((d["field_id"],k,m) in existing for k in range(1,6) for m in METHODS):
            continue
        wangle=warmup(d,args.mst_bin,args.full_bin)
        print(f"FIELD {idx+1}/{len(selected)} {d['field_id']} warmup={wangle}",flush=True)
        for repeat in range(1,repeats+1):
            order=(METHODS if (idx+repeat)%2==0 else METHODS[::-1])
            for place,method in enumerate(order,1):
                key=(d["field_id"],repeat,method)
                if key in existing:continue
                try:
                    v=evaluate(d,method,args.mst_bin,args.full_bin,authority[d["field_id"]])
                except Exception as e:
                    v={"status":"UNRESOLVED", "error":str(e)[:1000],
                       "authority_j_m":authority[d["field_id"]],"exact_to_authority":"false",
                       "unresolved_count":1}
                rec={**{k:"" for k in FIELDS},**v,"field_id":d["field_id"],
                     "family":d["family"],"repeat":repeat,"method":method,"order_in_repeat":place}
                append_row(runsfile,rec)
                existing[key]=rec
                print(f"  rep={repeat} {method} status={v['status']} wall={v.get('wall_seconds')} full={v.get('full_calls')}",flush=True)
                if v["status"]!="SUCCESS":
                    raise RuntimeError(f"Stop on {v['status']} at {key}. Details in {runsfile}")
    print("COMPLETED. For formal evaluation, run analyze with --input",runsfile)

def percentile(xs,q):
    xs=sorted(xs)
    pos=(len(xs)-1)*q
    low=int(math.floor(pos));high=int(math.ceil(pos));p=pos-low
    return xs[low]*(1-p)+xs[high]*p

def analyze(args):
    data=rows(args.input)
    if any(x.get("status")!="SUCCESS" or x.get("exact_to_authority")!="true" for x in data):
        raise ValueError("NO_GO: unresolved or inexact run present")
    mode="SMOKE" if args.input.name.startswith("smoke") else "FORMAL"
    if mode=="SMOKE" and not args.allow_smoke:raise ValueError("Smoke data cannot be used for a manuscript conclusion")
    by=defaultdict(dict)
    for x in data:
        k=(x["field_id"],int(x["repeat"]))
        m=x["method"]
        if m in by[k]:raise ValueError(f"Duplicate key {k}/{m}")
        by[k][m]=x
    field_groups=defaultdict(list)
    for (fid,rep),methods in by.items():
        if set(methods)!=set(METHODS):raise ValueError(f"Incomplete paired comparison {fid}/{rep}")
        field_groups[fid].append((rep,methods))
    expected=3 if mode=="SMOKE" else 18
    repcount=1 if mode=="SMOKE" else 5
    if len(field_groups)!=expected or len(data)!=expected*repcount*2:
        raise ValueError(f"Insufficient runs: {len(field_groups)} fields, {len(data)} rows; expected {expected*repcount*2}")
    fields=[]
    for fid,paired in sorted(field_groups.items()):
        if len(paired)!=repcount:raise ValueError(f"Incomplete repetitions for {fid}")
        r={"field_id":fid}
        for method in METHODS:
            times=[float(pair[method]["wall_seconds"]) for _,pair in paired]
            calls=[int(pair[method]["full_calls"]) for _,pair in paired]
            bound=[float(pair[method]["bound_wall_seconds"]) for _,pair in paired]
            if len(set(calls))!=1:raise ValueError(f"Non-deterministic Full calls for {fid}/{method}")
            r[f"median_{method}_s"]=statistics.median(times)
            r[f"median_{method}_bound_s"]=statistics.median(bound)
            r[f"calls_{method}"]=calls[0]
        r["lb1_over_lb0"]=r["median_LB1_MST_CERTIFIED_s"]/r["median_LB0_CERTIFIED_s"]
        r["paired_seconds_diff_lb1_minus_lb0"]=r["median_LB1_MST_CERTIFIED_s"]-r["median_LB0_CERTIFIED_s"]
        fields.append(r)
    a=sum(r["median_LB0_CERTIFIED_s"] for r in fields)
    b=sum(r["median_LB1_MST_CERTIFIED_s"] for r in fields)
    ratio=b/a
    # Cluster bootstrap by field: repetitions do not become independent observations.
    rng=random.Random(20261011)
    reps=10000
    boot=[]
    for _ in range(reps):
        chosen=[fields[rng.randrange(len(fields))] for _ in fields]
        boot.append(sum(r["median_LB1_MST_CERTIFIED_s"] for r in chosen)/sum(r["median_LB0_CERTIFIED_s"] for r in chosen))
    ci=[percentile(boot,.025),percentile(boot,.975)]
    if mode=="SMOKE":verdict="SMOKE_ONLY_NO_CLAIM"
    elif ratio<1 and ci[1]<1:verdict="LB1_E2E_SPEEDUP_SUPPORTED_IN_18_FIELD_DOMAIN"
    elif ratio>=1 and ci[0]>1:verdict="LB1_E2E_SLOWER_SUPPORTED_IN_18_FIELD_DOMAIN"
    else:verdict="INCONCLUSIVE_OR_NOT_FASTER_DO_NOT_CLAIM_E2E_SPEEDUP"
    result={"run_type":mode,"n_fields":len(fields),"repeats_per_method_field":repcount,
            "aggregate_sum_field_medians_lb0_s":a,"aggregate_sum_field_medians_lb1_s":b,
            "lb1_over_lb0_ratio":ratio,"lb1_relative_change_percent":100*(ratio-1),
            "field_cluster_bootstrap_95pct_ci_lb1_over_lb0":ci,
            "median_fieldwise_lb1_over_lb0":statistics.median(r["lb1_over_lb0"] for r in fields),
            "lb1_faster_field_count":sum(r["lb1_over_lb0"]<1 for r in fields),
            "total_full_calls_lb0":sum(r["calls_LB0_CERTIFIED"] for r in fields),
            "total_full_calls_lb1":sum(r["calls_LB1_MST_CERTIFIED"] for r in fields),
            "gate":verdict,
            "interpretation":"E2E on same executed 18 fields; do not extrapolate to 90 fields or claim floating point certification."}
    out=args.input.parent
    with (out/("m2_smoke_analysis.json" if mode=="SMOKE" else "m2_formal_analysis.json")).open("w",encoding="utf-8") as f:
        json.dump(result,f,indent=2,ensure_ascii=False)
    with (out/("m2_smoke_field_summary.csv" if mode=="SMOKE" else "m2_formal_field_summary.csv")).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(fields[0]));w.writeheader();w.writerows(fields)
    print(json.dumps(result,indent=2,ensure_ascii=False))

def cli():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    a=sub.add_parser("run")
    a.add_argument("--repo",type=Path,required=True,help="Public CLBOS reproducibility repo root")
    a.add_argument("--selection",type=Path,required=True,help="E3 original 18-field selection_freeze.csv")
    a.add_argument("--authority",type=Path,required=True,help="E3 archived runtime_runs.csv with oracle results")
    a.add_argument("--wkt-root",type=Path,required=True,help="Existing experiment root with selected_wkts/")
    a.add_argument("--mst-bin",type=Path,required=True,help="agri_f2c_mst_probe with --swath-only and --mst-probe")
    a.add_argument("--full-bin",type=Path,required=True,help="agri_f2c_runner")
    a.add_argument("--f2c-source",type=Path,help="Optional pinned Fields2Cover source checkout; strongly recommended")
    a.add_argument("--output",type=Path,required=True)
    a.add_argument("--smoke",action="store_true",help="3 fields x 1 repeat, never publish")
    a.add_argument("--force-new",action="store_true",help="Only allowed if output CSV does not yet exist")
    b=sub.add_parser("analyze")
    b.add_argument("--input",required=True,type=Path)
    b.add_argument("--allow-smoke",action="store_true")
    return p.parse_args()
if __name__=="__main__":
    args=cli()
    try:
        if args.command=="run":run(args)
        else:analyze(args)
    except Exception as e:
        print(f"M2_BLOCKED: {type(e).__name__}: {e}",file=sys.stderr)
        sys.exit(2)


