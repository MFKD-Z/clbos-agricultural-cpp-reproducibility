#!/usr/bin/env python3
import csv
import json
import math
import os
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
BIN = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve() / "Fields2Cover-build/agri_f2c_mst_probe"
OUT = ROOT / "clbos01_mst_hierarchical_42"
OUT.mkdir(exist_ok=True)

ACTIONS = OUT / "mst_actions.csv"
FIELD_SUMMARY = OUT / "field_summary.csv"
FAMILY_SUMMARY = OUT / "family_summary.csv"
OVERALL = OUT / "overall_summary.csv"

FRESH_SEL = ROOT / "clbos01_fresh_12_validation/selected_fresh_12_fields.csv"
EXP_SEL = ROOT / "clbos01_expanded_30_validation/selected_expanded_30_fields.csv"
FRESH_ORACLE = ROOT / "clbos01_fresh_12_validation/evaluations.csv"
EXP_ORACLE = ROOT / "clbos01_expanded_30_validation/exhaustive_full_evaluations.csv"

EPS = 1e-6
TOL = 1e-6
TIMEOUT = 900


def read_csv(path):
    if not path.exists():
        raise RuntimeError(f"Missing: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append(path, fields, row):
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
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


def load_inputs():
    selected = {}
    for p in [FRESH_SEL, EXP_SEL]:
        for r in read_csv(p):
            selected[r["field_id"]] = r

    oracle = {}
    for p in [FRESH_ORACLE, EXP_ORACLE]:
        for r in read_csv(p):
            status = r.get("status", "SUCCESS")
            err = r.get("error", "")
            if status == "SUCCESS":
                oracle[(r["field_id"], int(r["angle_deg"]))] = ("SUCCESS", r)
            elif status == "INFEASIBLE_NO_SWATHS" or (
                status == "FAILED" and "no swaths generated" in err
            ):
                oracle[(r["field_id"], int(r["angle_deg"]))] = ("INFEASIBLE_NO_SWATHS", r)

    if len(selected) != 42:
        raise RuntimeError(f"Expected 42 selected fields, got {len(selected)}")
    return selected, oracle


def main():
    if not BIN.exists():
        raise RuntimeError(f"Missing probe binary: {BIN}")

    selected, oracle = load_inputs()

    fields = [
        "field_id","family","angle_deg","status",
        "swath_count","swath_total_length_m","mst_connection_lb_m","mst_total_lb_m",
        "upstream_seconds","mst_seconds","mst_probe_total_seconds",
        "oracle_status","oracle_complete_path_length_m",
        "mst_le_j","lsw_le_mst","error",
    ]

    done = {}
    if ACTIONS.exists():
        for r in read_csv(ACTIONS):
            if r["status"] in {"SUCCESS", "INFEASIBLE_NO_SWATHS"}:
                done[(r["field_id"], int(r["angle_deg"]))] = r

    field_ids = sorted(selected)
    total = len(field_ids) * 36
    n = 0

    for fid in field_ids:
        meta = selected[fid]
        for angle in range(0, 180, 5):
            n += 1
            key = (fid, angle)
            if key in done:
                print(f"[{n}/{total}] {fid} angle={angle} RESUME_SKIP", flush=True)
                continue

            oracle_status, orow = oracle.get(key, ("MISSING", {}))
            try:
                p = subprocess.run(
                    [str(BIN), "--wkt-file", meta["local_wkt_path"],
                     "--angle-deg", str(angle), "--mst-probe"],
                    text=True, capture_output=True, timeout=TIMEOUT,
                )
                if p.returncode == 0:
                    d = json.loads(p.stdout)
                    lsw = float(d["swath_total_length_m"])
                    lmst = float(d["mst_total_lb_m"])
                    if oracle_status != "SUCCESS":
                        status = "OUTCOME_MISMATCH"
                        err = f"probe feasible but oracle={oracle_status}"
                        j = ""
                        legal = ""
                    else:
                        jv = float(orow["complete_path_length_m"])
                        status = "SUCCESS"
                        err = ""
                        j = f"{jv:.12f}"
                        legal = lmst <= jv + TOL

                    row = {
                        "field_id": fid, "family": meta["family"], "angle_deg": angle,
                        "status": status,
                        "swath_count": d["swath_count"],
                        "swath_total_length_m": f"{lsw:.12f}",
                        "mst_connection_lb_m": f"{float(d['mst_connection_lb_m']):.12f}",
                        "mst_total_lb_m": f"{lmst:.12f}",
                        "upstream_seconds": d["upstream_seconds"],
                        "mst_seconds": d["mst_seconds"],
                        "mst_probe_total_seconds": d["mst_probe_total_seconds"],
                        "oracle_status": oracle_status,
                        "oracle_complete_path_length_m": j,
                        "mst_le_j": legal,
                        "lsw_le_mst": lsw <= lmst + TOL,
                        "error": err,
                    }
                else:
                    err = p.stderr.strip()
                    if "no swaths generated" in err and oracle_status == "INFEASIBLE_NO_SWATHS":
                        row = {
                            "field_id": fid, "family": meta["family"], "angle_deg": angle,
                            "status": "INFEASIBLE_NO_SWATHS",
                            "oracle_status": oracle_status,
                            "error": "",
                        }
                    else:
                        row = {
                            "field_id": fid, "family": meta["family"], "angle_deg": angle,
                            "status": "FAILED", "oracle_status": oracle_status, "error": err,
                        }
            except Exception as e:
                row = {
                    "field_id": fid, "family": meta["family"], "angle_deg": angle,
                    "status": "DRIVER_ERROR", "oracle_status": oracle_status,
                    "error": repr(e),
                }

            append(ACTIONS, fields, row)
            print(
                f"[{n}/{total}] {fid} angle={angle} {row['status']} "
                f"{row.get('error','')[:100]}",
                flush=True,
            )
            if row["status"] in {"SUCCESS", "INFEASIBLE_NO_SWATHS"}:
                done[key] = row

    rows = read_csv(ACTIONS)
    latest = {}
    for r in rows:
        key = (r["field_id"], int(r["angle_deg"]))
        if r["status"] in {"SUCCESS", "INFEASIBLE_NO_SWATHS"}:
            latest[key] = r

    summaries = []
    for fid in field_ids:
        rr = [latest[(fid, a)] for a in range(0, 180, 5) if (fid, a) in latest]
        if len(rr) != 36:
            summaries.append({
                "field_id": fid, "family": selected[fid]["family"],
                "status": f"INCOMPLETE_{len(rr)}_OF_36",
            })
            continue

        feasible = [r for r in rr if r["status"] == "SUCCESS"]
        infeasible = [r for r in rr if r["status"] == "INFEASIBLE_NO_SWATHS"]

        if not feasible:
            summaries.append({
                "field_id": fid, "family": selected[fid]["family"],
                "status": "NO_FEASIBLE",
            })
            continue

        vals = []
        for r in feasible:
            vals.append({
                "angle": int(r["angle_deg"]),
                "lsw": float(r["swath_total_length_m"]),
                "lmst": float(r["mst_total_lb_m"]),
                "j": float(r["oracle_complete_path_length_m"]),
                "mst_t": float(r["mst_seconds"]),
                "probe_t": float(r["mst_probe_total_seconds"]),
            })

        legal = all(str(r["mst_le_j"]).lower() == "true" for r in feasible)
        nested = all(str(r["lsw_le_mst"]).lower() == "true" for r in feasible)
        jstar = min(v["j"] for v in vals)

        c0 = sum(v["lsw"] < jstar + EPS for v in vals)
        c1 = sum(v["lmst"] < jstar + EPS for v in vals)

        # For epsilon>0 under ideal exact arithmetic:
        # lazy hierarchy evaluates MST on C0 candidates and Full on C1 candidates.
        summaries.append({
            "field_id": fid,
            "family": selected[fid]["family"],
            "status": "COMPLETE",
            "feasible_orientation_count": len(feasible),
            "infeasible_no_swaths_count": len(infeasible),
            "j_star_m": f"{jstar:.12f}",
            "mst_admissible_all": legal,
            "nested_lsw_le_mst_all": nested,
            "c_eps_lsw": c0,
            "c_eps_mst": c1,
            "predicted_mst_evaluations_hierarchical": c0,
            "predicted_full_calls_lsw_only": c0,
            "predicted_full_calls_hierarchical": c1,
            "full_calls_saved_by_mst": c0 - c1,
            "full_call_reduction_vs_lsw_only": (
                f"{(c0-c1)/c0:.12f}" if c0 else ""
            ),
            "full_call_reduction_vs_exhaustive": f"{1-c1/len(feasible):.12f}",
            "rho_lsw": f"{c0/len(feasible):.12f}",
            "rho_mst": f"{c1/len(feasible):.12f}",
            "median_mst_seconds": f"{statistics.median(v['mst_t'] for v in vals):.9f}",
            "median_mst_probe_total_seconds": f"{statistics.median(v['probe_t'] for v in vals):.9f}",
        })

    atomic(FIELD_SUMMARY, summaries)

    complete = [r for r in summaries if r["status"] == "COMPLETE"]
    fam_rows = []
    for family in sorted(set(r["family"] for r in complete)):
        fr = [r for r in complete if r["family"] == family]
        fam_rows.append({
            "family": family,
            "field_count": len(fr),
            "admissible_count": sum(str(r["mst_admissible_all"]).lower()=="true" for r in fr),
            "median_c_lsw": statistics.median(int(r["c_eps_lsw"]) for r in fr),
            "median_c_mst": statistics.median(int(r["c_eps_mst"]) for r in fr),
            "median_full_call_reduction_vs_exhaustive": statistics.median(
                float(r["full_call_reduction_vs_exhaustive"]) for r in fr
            ),
            "worst_hierarchical_full_calls": max(int(r["predicted_full_calls_hierarchical"]) for r in fr),
        })
    atomic(FAMILY_SUMMARY, fam_rows)

    if complete:
        overall = [{
            "complete_fields": len(complete),
            "mst_admissible_fields": sum(str(r["mst_admissible_all"]).lower()=="true" for r in complete),
            "nested_bound_fields": sum(str(r["nested_lsw_le_mst_all"]).lower()=="true" for r in complete),
            "median_c_lsw": statistics.median(int(r["c_eps_lsw"]) for r in complete),
            "median_c_mst": statistics.median(int(r["c_eps_mst"]) for r in complete),
            "median_full_calls_lsw_only": statistics.median(int(r["predicted_full_calls_lsw_only"]) for r in complete),
            "median_full_calls_hierarchical": statistics.median(int(r["predicted_full_calls_hierarchical"]) for r in complete),
            "worst_full_calls_lsw_only": max(int(r["predicted_full_calls_lsw_only"]) for r in complete),
            "worst_full_calls_hierarchical": max(int(r["predicted_full_calls_hierarchical"]) for r in complete),
            "total_full_calls_lsw_only": sum(int(r["predicted_full_calls_lsw_only"]) for r in complete),
            "total_full_calls_hierarchical": sum(int(r["predicted_full_calls_hierarchical"]) for r in complete),
            "median_hierarchical_reduction_vs_exhaustive": statistics.median(
                float(r["full_call_reduction_vs_exhaustive"]) for r in complete
            ),
        }]
        atomic(OVERALL, overall)
    else:
        overall = []

    print("\n=== MST HIERARCHICAL 42-FIELD RESULT ===")
    for r in summaries:
        if r["status"] != "COMPLETE":
            print(r["field_id"], r["status"])
            continue
        print(
            f"{r['field_id']}: Ceps {r['c_eps_lsw']}->{r['c_eps_mst']} "
            f"Full {r['predicted_full_calls_lsw_only']}->{r['predicted_full_calls_hierarchical']} "
            f"feas={r['feasible_orientation_count']} "
            f"admissible={r['mst_admissible_all']}"
        )

    print("\n=== FAMILY ===")
    for r in fam_rows:
        print(
            f"{r['family']}: admissible={r['admissible_count']}/{r['field_count']} "
            f"median_C={r['median_c_lsw']}->{r['median_c_mst']} "
            f"worst_full={r['worst_hierarchical_full_calls']}"
        )

    if overall:
        o = overall[0]
        print(
            "\nOVERALL "
            f"ADMISSIBLE={o['mst_admissible_fields']}/{o['complete_fields']} "
            f"NESTED={o['nested_bound_fields']}/{o['complete_fields']} "
            f"MEDIAN_FULL={o['median_full_calls_lsw_only']}->{o['median_full_calls_hierarchical']} "
            f"WORST_FULL={o['worst_full_calls_lsw_only']}->{o['worst_full_calls_hierarchical']} "
            f"TOTAL_FULL={o['total_full_calls_lsw_only']}->{o['total_full_calls_hierarchical']} "
            f"MEDIAN_REDUCTION_EXHAUSTIVE={100*float(o['median_hierarchical_reduction_vs_exhaustive']):.1f}%"
        )
    print("Outputs:", OUT)


if __name__ == "__main__":
    main()
