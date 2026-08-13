#!/usr/bin/env python3
"""Recompute manuscript-facing v2-added statistics from packaged CSV evidence.

Standard library only. No Fields2Cover calls and no network access.

Outputs:
  outputs/tables/v2_added_recomputed.json
  outputs/tables/v2_added_recomputed.csv
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADD = ROOT / "additional_evidence"
OUT = ROOT / "outputs" / "tables"
OUT.mkdir(parents=True, exist_ok=True)

BOOT_N = 5000
SEED = 20260813


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def f(x):
    return float(str(x).strip())


def b(x):
    return str(x).strip().lower() in {"true", "1", "yes", "pass", "success", "exact"}


def percentile(xs, q):
    vals = sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    p = (len(vals) - 1) * q
    lo, hi = int(math.floor(p)), int(math.ceil(p))
    if lo == hi:
        return vals[lo]
    a = p - lo
    return vals[lo] * (1 - a) + vals[hi] * a


def ranks(xs):
    idx = sorted(enumerate(xs), key=lambda z: z[1])
    out = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i + 1
        while j < len(idx) and idx[j][1] == idx[i][1]:
            j += 1
        r = ((i + 1) + j) / 2.0
        for k in range(i, j):
            out[idx[k][0]] = r
        i = j
    return out


def pearson(xs, ys):
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    sx, sy = sum(x*x for x in dx), sum(y*y for y in dy)
    if sx <= 0 or sy <= 0:
        return None
    return sum(a*b for a, b in zip(dx, dy)) / math.sqrt(sx * sy)


def spearman(xs, ys):
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys)
             if x is not None and y is not None
             and math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 3:
        return None
    x, y = zip(*pairs)
    return pearson(ranks(x), ranks(y))


def bootstrap_rho(xs, ys, n=BOOT_N, seed=SEED):
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys)
             if x is not None and y is not None]
    rng = random.Random(seed)
    vals = []
    m = len(pairs)
    for _ in range(n):
        smp = [pairs[rng.randrange(m)] for _ in range(m)]
        r = spearman([a for a, _ in smp], [bb for _, bb in smp])
        if r is not None and math.isfinite(r):
            vals.append(r)
    return percentile(vals, 0.025), percentile(vals, 0.975)


def zscore(xs):
    m = sum(xs) / len(xs)
    ss = sum((x - m)**2 for x in xs)
    if ss <= 0:
        return None
    sd = math.sqrt(ss / (len(xs) - 1))
    return [(x - m) / sd for x in xs]


def solve(A, bvec):
    n = len(A)
    M = [list(map(float, A[i])) + [float(bvec[i])] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]
        for j in range(c, n + 1):
            M[c][j] /= pv
        for r in range(n):
            if r == c:
                continue
            fac = M[r][c]
            for j in range(c, n + 1):
                M[r][j] -= fac * M[c][j]
    return [M[i][n] for i in range(n)]


def ols(rows, xkeys):
    clean = []
    for r in rows:
        y = f(r["Nfull"])
        xs = [f(r[k]) for k in xkeys]
        tx = [math.log1p(max(0.0, v)) if k == "median_lsw_m" else v
              for k, v in zip(xkeys, xs)]
        clean.append((math.log1p(max(0.0, y)), tx))
    n = len(clean)
    p = len(xkeys) + 1
    yv = [y for y, _ in clean]
    cols = list(zip(*[x for _, x in clean]))
    zcols = [zscore(c) for c in cols]
    if any(c is None for c in zcols):
        return {"status": "SINGULAR"}
    X = [[1.0] + [zcols[j][i] for j in range(len(zcols))] for i in range(n)]
    XtX = [[0.0]*p for _ in range(p)]
    Xty = [0.0]*p
    for i in range(n):
        for a in range(p):
            Xty[a] += X[i][a] * yv[i]
            for bb in range(p):
                XtX[a][bb] += X[i][a] * X[i][bb]
    beta = solve(XtX, Xty)
    if beta is None:
        return {"status": "SINGULAR"}
    pred = [sum(beta[j] * X[i][j] for j in range(p)) for i in range(n)]
    ym = sum(yv) / n
    sse = sum((y-yh)**2 for y, yh in zip(yv, pred))
    sst = sum((y-ym)**2 for y in yv)
    r2 = 1 - sse/sst
    adj = 1 - (1-r2)*(n-1)/(n-p)
    return {
        "status": "OK",
        "n": n,
        "r2": r2,
        "adjusted_r2": adj,
        "standardized_betas": {k: beta[i+1] for i, k in enumerate(xkeys)},
    }


def e1():
    rows = read_csv(ADD / "e1_transfer" / "data" / "transfer_results.csv")
    by = defaultdict(list)
    for r in rows:
        by[r["experiment_arm"]].append(r)
    out = {}
    for arm in ("T1", "T2", "T3"):
        rr = by[arm]
        ranks_ = [int(round(f(r["top10_oracle_rank"]))) for r in rr]
        out[arm] = {
            "fields": len(rr),
            "top10_exact": sum(b(r["top10_exact"]) for r in rr),
            "clbos_exact": sum(b(r["clbos_exact"]) for r in rr),
            "retrospective_kmin": max(ranks_),
            "clbos_full_calls": sum(int(round(f(r["clbos_Nfull"]))) for r in rr),
            "top10_full_calls": sum(int(round(f(r["top10_Nfull"]))) for r in rr),
        }
    return out


def e2():
    rows = read_csv(ADD / "e2_vehicle_sensitivity" / "data" / "paired_turn_radius_analysis.csv")
    deltan = [f(r["delta_Nfull"]) for r in rows]
    deltag = [f(r["delta_p90_abs_gap_m"]) for r in rows]
    return {
        "paired_fields": len(rows),
        "nfull_A_total": int(sum(f(r["Nfull_A"]) for r in rows)),
        "nfull_B_total": int(sum(f(r["Nfull_B"]) for r in rows)),
        "nfull_increase_count": sum(x > 0 for x in deltan),
        "nfull_same_count": sum(x == 0 for x in deltan),
        "nfull_decrease_count": sum(x < 0 for x in deltan),
        "median_delta_p90_abs_gap_m": statistics.median(deltag),
        "rho_delta_p90_gap_delta_nfull": spearman(deltag, deltan),
    }


def e2_secondary():
    rows = read_csv(ADD / "e2_secondary_mechanism" / "data" / "t1_field_metrics.csv")
    nfull = [f(r["Nfull"]) for r in rows]
    rel = [f(r["p90_rel_gap"]) for r in rows]
    abs_ = [f(r["p90_abs_gap_m"]) for r in rows]
    lsw = [f(r["median_lsw_m"]) for r in rows]
    feasible = [f(r["feasible_orientation_count"]) for r in rows]
    ci = bootstrap_rho(nfull, rel)
    G = ols(rows, ["median_lsw_m", "feasible_orientation_count"])
    M = ols(rows, ["p90_rel_gap"])
    GM = ols(rows, ["median_lsw_m", "feasible_orientation_count", "p90_rel_gap"])
    return {
        "fields": len(rows),
        "rho_nfull_p90_relative_gap": spearman(nfull, rel),
        "rho_nfull_p90_relative_gap_bootstrap95": list(ci),
        "rho_nfull_p90_absolute_gap": spearman(nfull, abs_),
        "rho_nfull_median_lsw": spearman(nfull, lsw),
        "rho_nfull_feasible_orientation_count": spearman(nfull, feasible),
        "geometry_proxy_adjusted_r2": G.get("adjusted_r2"),
        "gap_only_adjusted_r2": M.get("adjusted_r2"),
        "combined_adjusted_r2": GM.get("adjusted_r2"),
        "combined_gap_standardized_beta": GM.get("standardized_betas", {}).get("p90_rel_gap"),
    }


def e3():
    rows = read_csv(ADD / "e3_runtime" / "data" / "runtime_runs.csv")
    summary = read_csv(ADD / "e3_runtime" / "data" / "field_runtime_summary.csv")
    by_rep_method = defaultdict(float)
    for r in rows:
        if r["status"] == "SUCCESS":
            by_rep_method[(int(r["repeat"]), r["method"])] += f(r["wall_seconds"])
    vals = defaultdict(list)
    for (rep, method), value in sorted(by_rep_method.items()):
        vals[method].append(value)
    agg_ex = statistics.median(vals["EXHAUSTIVE"])
    agg_cl = statistics.median(vals["CLBOS_MST"])
    agg_top = statistics.median(vals["TOP10_LSW_PRECOMPUTED"])
    speedups = [f(r["clbos_speedup_vs_exhaustive"]) for r in summary]
    return {
        "fields": len(summary),
        "repeats": len(set(int(r["repeat"]) for r in rows)),
        "failed_runs": sum(r["status"] != "SUCCESS" for r in rows),
        "clbos_exact_fields": sum(b(r["all_clbos_exact"]) for r in summary),
        "top10_exact_fields": sum(b(r["all_top10_exact"]) for r in summary),
        "clbos_faster_fields": sum(f(r["median_clbos_seconds"]) < f(r["median_exhaustive_seconds"]) for r in summary),
        "median_field_speedup_vs_exhaustive": statistics.median(speedups),
        "aggregate_exhaustive_seconds": agg_ex,
        "aggregate_clbos_seconds": agg_cl,
        "aggregate_top10_downstream_only_seconds": agg_top,
        "aggregate_speedup_vs_exhaustive": agg_ex / agg_cl,
        "aggregate_runtime_reduction_vs_exhaustive": 1.0 - agg_cl / agg_ex,
        "median_bound_acquisition_fraction": statistics.median(f(r["median_clbos_bound_fraction"]) for r in summary),
        "median_clbos_full_calls": statistics.median(f(r["median_clbos_full_calls"]) for r in summary),
        "clbos_to_favourable_top10_ratio": agg_cl / agg_top,
    }


def flatten(prefix, obj, rows):
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(f"{prefix}.{k}" if prefix else k, v, rows)
    elif isinstance(obj, list):
        rows.append({"metric": prefix, "value": json.dumps(obj)})
    else:
        rows.append({"metric": prefix, "value": obj})


def main():
    result = {"E1": e1(), "E2": e2(), "E2_secondary": e2_secondary(), "E3": e3()}
    json_path = OUT / "v2_added_recomputed.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    flat = []
    flatten("", result, flat)
    csv_path = OUT / "v2_added_recomputed.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fobj:
        w = csv.DictWriter(fobj, fieldnames=["metric", "value"])
        w.writeheader()
        w.writerows(flat)
    print(json.dumps(result, indent=2))
    print(f"WROTE={json_path}")
    print(f"WROTE={csv_path}")


if __name__ == "__main__":
    main()
