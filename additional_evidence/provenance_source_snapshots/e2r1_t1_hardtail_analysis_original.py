# PUBLIC NOTE: path-sanitized source snapshot of the executed experiment script; not the portable reproduction entry point.
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLBOS E2-R1 — T1 60-field hard-tail mechanism analysis
======================================================

Purpose
-------
Use ONLY already-computed E1 T1 outcome-blind exhaustive data to test whether
field-level certificate relaxation tightness is associated with CLBOS Nfull.

No new Fields2Cover calls.
No new Route+Path calls.
No method/manuscript/public-release modification.
Standard-library only.

Primary response:
    Nfull

Primary mechanism descriptor:
    field P90 relative relaxation gap
      (J(theta) - LB1(theta)) / J(theta)

Scale proxies:
    median Lsw
    feasible orientation count

Models (descriptive, not deployment predictors):
    G  : log1p(Nfull) ~ log1p(median_Lsw) + feasible_count
    M  : log1p(Nfull) ~ P90_relative_gap
    GM : log1p(Nfull) ~ log1p(median_Lsw) + feasible_count + P90_relative_gap

Classification:
    STRONG if:
      - exhaustive T1 angle coverage verified,
      - zero bound violations,
      - rho(Nfull, P90 rel gap) > 0,
      - abs(rho_gap) >= max(abs(rho_scale), abs(rho_feasible)),
      - combined adjusted R2 >= geometry-proxy adjusted R2 + 0.05,
      - standardized gap beta in combined model > 0.

    PARTIAL if:
      - rho_gap > 0 and combined standardized gap beta > 0,
      but strong conditions are not all met.

    NOT_SUPPORTED otherwise.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TOL = 1e-6
BOOT_N = 5000
SEED = 20260813


def fnum(x):
    try:
        v = float(str(x).strip())
        return v if math.isfinite(v) else None
    except Exception:
        return None


def inum(x):
    v = fnum(x)
    return int(round(v)) if v is not None else None


def is_success(s):
    x = str(s or "").strip().lower()
    if not x:
        return True
    return ("success" in x or "complete" in x or "valid" in x) and not any(
        k in x for k in ("fail", "error", "timeout", "infeasible")
    )


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]]):
    keys = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            out = {}
            for k in keys:
                v = r.get(k)
                if isinstance(v, float):
                    out[k] = f"{v:.12g}"
                elif v is None:
                    out[k] = ""
                else:
                    out[k] = v
            w.writerow(out)


def angle_key(x):
    v = fnum(x)
    return round(v, 8) if v is not None else None


def percentile(xs: Sequence[float], q: float):
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


def median(xs):
    vals = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(vals) if vals else None


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
    if len(pairs) < 4:
        return (None, None)
    rng = random.Random(seed)
    vals = []
    m = len(pairs)
    for _ in range(n):
        smp = [pairs[rng.randrange(m)] for _ in range(m)]
        r = spearman([a for a, _ in smp], [b for _, b in smp])
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


def solve(A, b):
    n = len(A)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
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
            f = M[r][c]
            for j in range(c, n + 1):
                M[r][j] -= f * M[c][j]
    return [M[i][n] for i in range(n)]


def ols(rows, xkeys):
    clean = []
    for r in rows:
        y = fnum(r.get("Nfull"))
        xs = [fnum(r.get(k)) for k in xkeys]
        if y is None or any(v is None for v in xs):
            continue
        tx = []
        for k, v in zip(xkeys, xs):
            if k == "median_lsw_m":
                tx.append(math.log1p(max(0.0, v)))
            else:
                tx.append(v)
        clean.append((math.log1p(max(0.0, y)), tx))
    n = len(clean)
    p = len(xkeys) + 1
    if n <= p + 1:
        return {"status": "INSUFFICIENT_N", "n": n}

    yv = [y for y, _ in clean]
    cols = list(zip(*[x for _, x in clean]))
    zcols = []
    for c in cols:
        z = zscore(c)
        if z is None:
            return {"status": "SINGULAR", "n": n}
        zcols.append(z)

    X = [[1.0] + [zcols[j][i] for j in range(len(zcols))] for i in range(n)]
    XtX = [[0.0]*p for _ in range(p)]
    Xty = [0.0]*p
    for i in range(n):
        for a in range(p):
            Xty[a] += X[i][a]*yv[i]
            for b in range(p):
                XtX[a][b] += X[i][a]*X[i][b]
    beta = solve(XtX, Xty)
    if beta is None:
        return {"status": "SINGULAR", "n": n}
    pred = [sum(beta[j]*X[i][j] for j in range(p)) for i in range(n)]
    ym = sum(yv)/n
    sse = sum((y-yh)**2 for y, yh in zip(yv, pred))
    sst = sum((y-ym)**2 for y in yv)
    r2 = 1 - sse/sst if sst > 0 else None
    adj = 1 - (1-r2)*(n-1)/(n-p) if r2 is not None and n > p else None
    return {
        "status": "OK",
        "n": n,
        "xkeys": xkeys,
        "standardized_betas": {k: beta[i+1] for i, k in enumerate(xkeys)},
        "r2": r2,
        "adjusted_r2": adj,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default="/path/to/agri_cross_module_canary")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    e1 = root / "E1_FROZEN_K_TRANSFER"
    out = root / "E2_CERTIFICATION_MECHANISM" / "E2R1_T1_HARDTAIL"
    out.mkdir(parents=True, exist_ok=True)

    transfer_p = e1 / "04_E1_TRANSFER_RESULTS.csv"
    bounds_p = e1 / "raw" / "candidate_bounds.csv"
    paths_p = e1 / "raw" / "candidate_full_paths.csv"
    for p in (transfer_p, bounds_p, paths_p):
        if not p.exists():
            raise FileNotFoundError(p)

    transfer = read_csv(transfer_p)
    bounds = read_csv(bounds_p)
    paths = read_csv(paths_p)

    t1_summary = {
        r["source_sha256"]: r for r in transfer
        if r.get("experiment_arm") == "T1"
    }

    bidx = {}
    for r in bounds:
        if r.get("experiment_arm") != "T1" or not is_success(r.get("status")):
            continue
        sha, ang = r.get("source_sha256"), angle_key(r.get("angle_deg"))
        lsw, lb1 = fnum(r.get("swath_total_length_m")), fnum(r.get("mst_total_lb_m"))
        if sha and ang is not None and lsw is not None and lb1 is not None:
            bidx[(sha, ang)] = (lsw, lb1)

    jidx = {}
    for r in paths:
        if r.get("experiment_arm") != "T1" or not is_success(r.get("status")):
            continue
        sha, ang = r.get("source_sha256"), angle_key(r.get("angle_deg"))
        J = fnum(r.get("complete_path_length_m"))
        if sha and ang is not None and J is not None:
            jidx[(sha, ang)] = J

    rows = []
    bound_viol = 0
    total_bound_success = 0
    total_matched = 0
    incomplete_fields = []

    for sha, sr in sorted(t1_summary.items(), key=lambda z: z[1].get("field_id", "")):
        bangs = {ang for sh, ang in bidx if sh == sha}
        jangs = {ang for sh, ang in jidx if sh == sha}
        matched = sorted(bangs & jangs)
        total_bound_success += len(bangs)
        total_matched += len(matched)
        if bangs != jangs:
            incomplete_fields.append({
                "field_id": sr.get("field_id"),
                "source_sha256": sha,
                "bound_success_angles": len(bangs),
                "full_path_angles": len(jangs),
                "matched_angles": len(matched),
                "missing_J_for_bound": len(bangs - jangs),
                "J_without_bound": len(jangs - bangs),
            })

        gaps, rels, captures, lsws = [], [], [], []
        for ang in matched:
            lsw, lb1 = bidx[(sha, ang)]
            J = jidx[(sha, ang)]
            gap = J - lb1
            if gap < -TOL:
                bound_viol += 1
            rel = gap / J if J > TOL else None
            tmst = lb1 - lsw
            nonwork = J - lsw
            cap = tmst / nonwork if nonwork > TOL else None
            gaps.append(gap)
            if rel is not None:
                rels.append(rel)
            if cap is not None:
                captures.append(cap)
            lsws.append(lsw)

        rows.append({
            "field_id": sr.get("field_id"),
            "source_sha256": sha,
            "Nfull": inum(sr.get("clbos_Nfull")),
            "candidate_count": inum(sr.get("candidate_count")),
            "feasible_orientation_count": len(matched),
            "oracle_J_m": fnum(sr.get("oracle_J")),
            "median_lsw_m": median(lsws),
            "median_abs_gap_m": median(gaps),
            "p90_abs_gap_m": percentile(gaps, 0.90),
            "median_rel_gap": median(rels),
            "p90_rel_gap": percentile(rels, 0.90),
            "median_mst_capture_ratio": median(captures),
        })

    coverage = total_matched / total_bound_success if total_bound_success else 0.0
    exhaustive_pass = (
        len(rows) == 60
        and len(incomplete_fields) == 0
        and abs(coverage - 1.0) <= 1e-12
    )

    def rho(key):
        pairs = [
            (fnum(r.get(key)), fnum(r.get("Nfull")))
            for r in rows
            if fnum(r.get(key)) is not None and fnum(r.get("Nfull")) is not None
        ]
        return spearman([a for a, _ in pairs], [b for _, b in pairs])

    rho_gap = rho("p90_rel_gap")
    rho_abs = rho("p90_abs_gap_m")
    rho_lsw = rho("median_lsw_m")
    rho_feas = rho("feasible_orientation_count")

    pairs_gap = [
        (fnum(r["p90_rel_gap"]), fnum(r["Nfull"]))
        for r in rows
        if fnum(r["p90_rel_gap"]) is not None and fnum(r["Nfull"]) is not None
    ]
    rho_gap_ci = bootstrap_rho(
        [a for a, _ in pairs_gap],
        [b for _, b in pairs_gap],
    )

    G = ols(rows, ["median_lsw_m", "feasible_orientation_count"])
    M = ols(rows, ["p90_rel_gap"])
    GM = ols(rows, ["median_lsw_m", "feasible_orientation_count", "p90_rel_gap"])

    gap_beta = None
    if GM.get("status") == "OK":
        gap_beta = GM.get("standardized_betas", {}).get("p90_rel_gap")

    strongest_simple = max(abs(x) for x in (rho_lsw, rho_feas) if x is not None)
    adjG = G.get("adjusted_r2") if G.get("status") == "OK" else None
    adjGM = GM.get("adjusted_r2") if GM.get("status") == "OK" else None
    adds = (
        adjG is not None and adjGM is not None
        and adjGM >= adjG + 0.05
    )

    if not exhaustive_pass:
        status = "H2_T1_BLOCKED_INCOMPLETE_EXHAUSTIVE_COVERAGE"
    elif bound_viol > 0:
        status = "H2_T1_CERTIFICATE_ANOMALY"
    elif (
        rho_gap is not None and rho_gap > 0
        and abs(rho_gap) >= strongest_simple
        and adds
        and gap_beta is not None and gap_beta > 0
    ):
        status = "H2_T1_STRONG_MECHANISM_ASSOCIATION"
    elif rho_gap is not None and rho_gap > 0 and gap_beta is not None and gap_beta > 0:
        status = "H2_T1_PARTIAL_MECHANISM_ASSOCIATION"
    else:
        status = "H2_T1_NOT_SUPPORTED"

    write_csv(out / "07_E2R1_T1_FIELD_METRICS.csv", rows)

    report = f"""# E2-R1 Scientific Report — T1 60-field hard-tail mechanism

## Integrity

- T1 field count: **{len(rows)}**
- Successful bound field-angle rows: **{total_bound_success}**
- Matched exhaustive J(theta) rows: **{total_matched}**
- Coverage fraction: **{coverage:.12f}**
- Incomplete field count: **{len(incomplete_fields)}**
- Bound violation count: **{bound_viol}**
- New Route+Path calls: **0**

## Field-level associations with CLBOS Nfull

- Spearman rho(Nfull, P90 relative relaxation gap): **{rho_gap}**
- Bootstrap 95% CI: **[{rho_gap_ci[0]}, {rho_gap_ci[1]}]**
- Spearman rho(Nfull, P90 absolute relaxation gap): **{rho_abs}**
- Spearman rho(Nfull, median Lsw): **{rho_lsw}**
- Spearman rho(Nfull, feasible orientation count): **{rho_feas}**

## Descriptive models

Geometry/scale proxy model:
`log1p(Nfull) ~ log1p(median Lsw) + feasible orientation count`

```json
{json.dumps(G, ensure_ascii=False, indent=2)}
```

Mechanism-only model:
`log1p(Nfull) ~ P90 relative relaxation gap`

```json
{json.dumps(M, ensure_ascii=False, indent=2)}
```

Combined model:
`log1p(Nfull) ~ log1p(median Lsw) + feasible orientation count + P90 relative relaxation gap`

```json
{json.dumps(GM, ensure_ascii=False, indent=2)}
```

## Scientific classification

`H2_T1_STATUS={status}`

This is a secondary mechanism analysis of an outcome-blind T1 field population.
It does not restore the missing three-family analysis of the original balanced 90-field set.
"""

    (out / "08_E2R1_T1_SCIENTIFIC_REPORT.md").write_text(report, encoding="utf-8")

    gate = {
        "TASK_STATUS": "COMPLETE",
        "NEW_ROUTE_PATH_CALL_COUNT": 0,
        "METHOD_MODIFIED": False,
        "MANUSCRIPT_MODIFIED": False,
        "T1_FIELD_COUNT": len(rows),
        "T1_BOUND_SUCCESS_FIELD_ANGLE_COUNT": total_bound_success,
        "T1_MATCHED_EXHAUSTIVE_J_FIELD_ANGLE_COUNT": total_matched,
        "T1_EXHAUSTIVE_COVERAGE_FRACTION": coverage,
        "T1_INCOMPLETE_FIELD_COUNT": len(incomplete_fields),
        "BOUND_VIOLATION_COUNT": bound_viol,
        "RHO_NFULL_P90_REL_GAP": rho_gap,
        "RHO_NFULL_P90_REL_GAP_BOOTSTRAP95": list(rho_gap_ci),
        "RHO_NFULL_P90_ABS_GAP": rho_abs,
        "RHO_NFULL_MEDIAN_LSW": rho_lsw,
        "RHO_NFULL_FEASIBLE_ORIENTATION_COUNT": rho_feas,
        "GEOMETRY_PROXY_MODEL": G,
        "MECHANISM_MODEL": M,
        "COMBINED_MODEL": GM,
        "H2_T1_STATUS": status,
        "INCOMPLETE_FIELDS": incomplete_fields,
    }
    with (out / "09_E2R1_T1_GATE.json").open("w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False, indent=2)

    print("TASK_STATUS=COMPLETE")
    print("NEW_ROUTE_PATH_CALL_COUNT=0")
    print(f"T1_FIELD_COUNT={len(rows)}")
    print(f"T1_EXHAUSTIVE_COVERAGE_FRACTION={coverage}")
    print(f"T1_INCOMPLETE_FIELD_COUNT={len(incomplete_fields)}")
    print(f"BOUND_VIOLATION_COUNT={bound_viol}")
    print(f"RHO_NFULL_P90_REL_GAP={rho_gap}")
    print(f"RHO_NFULL_P90_REL_GAP_BOOTSTRAP95={rho_gap_ci}")
    print(f"RHO_NFULL_MEDIAN_LSW={rho_lsw}")
    print(f"RHO_NFULL_FEASIBLE_ORIENTATION_COUNT={rho_feas}")
    print(f"GEOMETRY_PROXY_ADJ_R2={G.get('adjusted_r2')}")
    print(f"MECHANISM_ADJ_R2={M.get('adjusted_r2')}")
    print(f"COMBINED_ADJ_R2={GM.get('adjusted_r2')}")
    print(f"H2_T1_STATUS={status}")
    print(str(out / "08_E2R1_T1_SCIENTIFIC_REPORT.md"))
    print(str(out / "09_E2R1_T1_GATE.json"))


if __name__ == "__main__":
    main()
