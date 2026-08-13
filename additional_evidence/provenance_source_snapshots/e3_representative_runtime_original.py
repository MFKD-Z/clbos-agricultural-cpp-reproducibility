# PUBLIC NOTE: path-sanitized source snapshot of the executed experiment script; not the portable reproduction entry point.
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLBOS E3 — Representative Runtime Evaluation
=============================================

Scientific purpose
------------------
Measure representative 1-degree runtime on 18 deterministically selected fields:

  M1 EXHAUSTIVE
     End-to-end Python driver wall clock, including subprocess overhead.

  M2 CLBOS_MST
     End-to-end Python driver wall clock, including:
       - all 180 MST bound probes,
       - selected complete Route+Path evaluations.
     This intentionally preserves the prior conservative implementation:
     selected Full calls recompute their own upstream work.

  M3 TOP10_LSW_PRECOMPUTED
     Frozen SwathLength Top-10 selected from the authoritative precomputed
     1-degree bound table. Timing includes ONLY the ten downstream Full calls.
     This deliberately favors Top-10 and is therefore NOT an end-to-end
     apples-to-apples timing estimate. CLBOS-vs-Top10 is interpreted as a
     conservative upper bound on certification premium.

Selection
---------
From the existing 90-field held-out set:
  - exclude the 9 fields already used in prior resolution-scaling timing,
  - within each of the three geometry families, sort by (area_m2, field_id),
  - choose six deterministic equal-rank-bin midpoints,
  - 18 fields total.

No runtime/outcome value enters E3 selection.

Safety
------
- New output directory only.
- No modification of manuscript, method, historical results, GitHub or Zenodo.
- No algorithm retuning.
- Standard Python library only.
- Resumable: successful run keys are skipped.

Expected working directory when invoked:
  /path/to/agri_cross_module_canary
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


EXPECTED_F2C_HEAD = "92b9f2fcf72d26c44202f9d2ab54fbf25ed87426"
TIMEOUT = 900
EPS = 1e-6
EXACT_TOL_M = 1e-6
REPEATS_DEFAULT = 5
K = 10
FAMILY_TARGET = 6
CANDIDATE_COUNT = 180

METHODS = ("CLBOS_MST", "EXHAUSTIVE", "TOP10_LSW_PRECOMPUTED")
PERMUTATIONS = list(itertools.permutations(METHODS))


def sha256_file(path: Path, chunk=1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def append_csv(path: Path, fields: List[str], row: Dict[str, Any]) -> None:
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def atomic_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    keys: List[str] = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def percentile(vals: Sequence[float], q: float) -> float:
    xs = sorted(float(x) for x in vals)
    if not xs:
        return math.nan
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    a = pos - lo
    return xs[lo] * (1 - a) + xs[hi] * a


def iqr(vals: Sequence[float]) -> float:
    return percentile(vals, 0.75) - percentile(vals, 0.25)


def fnum(x: Any) -> Optional[float]:
    try:
        v = float(str(x).strip())
        return v if math.isfinite(v) else None
    except Exception:
        return None


def angles() -> List[int]:
    return list(range(180))


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def run_json(cmd: List[str]) -> Dict[str, Any]:
    p = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=TIMEOUT,
    )
    if p.returncode != 0:
        err = (p.stderr or "").strip()
        raise RuntimeError(err or f"nonzero return code {p.returncode}")
    return json.loads(p.stdout)


def equal_rank_midpoints(rows: List[Dict[str, str]], n: int) -> List[Dict[str, str]]:
    """Choose midpoint of each of n equal rank bins after deterministic sorting."""
    rr = sorted(rows, key=lambda r: (float(r["area_m2"]), r["field_id"]))
    N = len(rr)
    if N < n:
        raise RuntimeError(f"Cannot select {n} from only {N}")
    chosen = []
    used = set()
    for i in range(n):
        start = i * N / n
        end = (i + 1) * N / n
        idx = int(math.floor((start + end) / 2.0))
        if idx >= N:
            idx = N - 1
        # Deterministically resolve pathological duplicate midpoint index.
        while idx in used and idx + 1 < N:
            idx += 1
        while idx in used and idx - 1 >= 0:
            idx -= 1
        used.add(idx)
        row = dict(rr[idx])
        row["e3_family_rank_zero_based"] = idx
        row["e3_family_pool_size_after_prior_timing_exclusion"] = N
        row["e3_selection_bin_zero_based"] = i
        row["e3_selection_rule"] = (
            "EXCLUDE_PRIOR_9_TIMING_FIELDS_THEN_6_EQUAL_AREA_RANK_BIN_MIDPOINTS_PER_FAMILY"
        )
        chosen.append(row)
    return chosen


def build_selection(
    selected90: List[Dict[str, str]],
    prior9: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    if len(selected90) != 90:
        raise RuntimeError(f"Expected 90 held-out metadata rows, got {len(selected90)}")
    required = {"field_id", "family", "area_m2", "local_wkt_path"}
    if not required.issubset(selected90[0].keys()):
        raise RuntimeError(f"selected_heldout_fields.csv missing required columns: {required}")

    prior_ids = {r["field_id"] for r in prior9}
    eligible = [r for r in selected90 if r["field_id"] not in prior_ids]

    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in eligible:
        groups[r["family"]].append(r)

    expected_families = {
        "CONVEX_NO_HOLES",
        "NONCONVEX_NO_HOLES",
        "HAS_HOLES_OR_INTERNAL_OBSTACLES",
    }
    if set(groups) != expected_families:
        raise RuntimeError(f"Unexpected held-out families: {sorted(groups)}")

    out = []
    for fam in sorted(expected_families):
        selected = equal_rank_midpoints(groups[fam], FAMILY_TARGET)
        for r in selected:
            r["e3_prior_timing_excluded_count_total"] = len(prior_ids)
        out.extend(selected)

    if len(out) != 18 or len({r["field_id"] for r in out}) != 18:
        raise RuntimeError("E3 selection did not yield 18 unique fields")
    return out


def load_bound_rankings(bound_path: Path) -> Tuple[Dict[str, List[Tuple[float, float, float]]], Dict[str, int]]:
    """
    Return field -> list of (lsw, angle, mst_lb), sorted later.
    Only SUCCESS orientations are retained.
    """
    br: Dict[str, List[Tuple[float, float, float]]] = defaultdict(list)
    infeas: Dict[str, int] = defaultdict(int)
    for r in read_csv(bound_path):
        fid = r.get("field_id", "")
        st = r.get("status", "")
        if st == "SUCCESS":
            br[fid].append((
                float(r["swath_total_length_m"]),
                float(r["angle_deg"]),
                float(r["mst_total_lb_m"]),
            ))
        elif st == "INFEASIBLE_NO_SWATHS":
            infeas[fid] += 1
    for fid in br:
        br[fid].sort(key=lambda z: (z[0], z[1]))
    return br, infeas


def warmup(field: Dict[str, str], feasible_angles: List[Tuple[float, float, float]], mst_bin: Path, full_bin: Path) -> None:
    if not feasible_angles:
        raise RuntimeError(f"No known feasible angle for warmup: {field['field_id']}")
    # Use best-Lsw feasible angle to avoid angle-0 no-swath failures.
    _, a, _ = feasible_angles[0]
    run_json([
        str(mst_bin), "--wkt-file", field["local_wkt_path"],
        "--angle-deg", str(a), "--mst-probe",
    ])
    run_json([
        str(full_bin), "--wkt-file", field["local_wkt_path"],
        "--angle-deg", str(a),
    ])


def run_exhaustive(field: Dict[str, str], full_bin: Path) -> Dict[str, Any]:
    t0 = time.monotonic()
    best = math.inf
    success = 0
    infeas = 0
    for a in angles():
        try:
            d = run_json([
                str(full_bin), "--wkt-file", field["local_wkt_path"],
                "--angle-deg", str(a),
            ])
            success += 1
            best = min(best, float(d["complete_path_length_m"]))
        except RuntimeError as e:
            if "no swaths generated" in str(e):
                infeas += 1
            else:
                raise
    wall = time.monotonic() - t0
    if not math.isfinite(best):
        raise RuntimeError("Exhaustive produced no finite incumbent")
    return {
        "wall_seconds": wall,
        "bound_wall_seconds": 0.0,
        "selected_full_wall_seconds": wall,
        "full_calls": success,
        "feasible_count": success,
        "infeasible_count": infeas,
        "j_star_m": best,
    }


def run_clbos(field: Dict[str, str], mst_bin: Path, full_bin: Path) -> Dict[str, Any]:
    method_t0 = time.monotonic()
    bound_t0 = time.monotonic()
    br: List[Tuple[float, float]] = []
    infeas = 0

    for a in angles():
        try:
            d = run_json([
                str(mst_bin), "--wkt-file", field["local_wkt_path"],
                "--angle-deg", str(a), "--mst-probe",
            ])
            br.append((float(d["mst_total_lb_m"]), float(a)))
        except RuntimeError as e:
            if "no swaths generated" in str(e):
                infeas += 1
            else:
                raise

    bound_wall = time.monotonic() - bound_t0
    br.sort(key=lambda z: (z[0], z[1]))

    U = math.inf
    calls = 0
    full_t0 = time.monotonic()
    for lb, a in br:
        if lb >= U + EPS:
            break
        d = run_json([
            str(full_bin), "--wkt-file", field["local_wkt_path"],
            "--angle-deg", str(a),
        ])
        calls += 1
        U = min(U, float(d["complete_path_length_m"]))
    full_wall = time.monotonic() - full_t0
    wall = time.monotonic() - method_t0

    if not math.isfinite(U):
        raise RuntimeError("CLBOS produced no finite incumbent")

    return {
        "wall_seconds": wall,
        "bound_wall_seconds": bound_wall,
        "selected_full_wall_seconds": full_wall,
        "full_calls": calls,
        "feasible_count": len(br),
        "infeasible_count": infeas,
        "j_star_m": U,
    }


def run_top10_precomputed(
    field: Dict[str, str],
    ranking: List[Tuple[float, float, float]],
    full_bin: Path,
) -> Dict[str, Any]:
    chosen = ranking[: min(K, len(ranking))]
    if not chosen:
        raise RuntimeError("Top10 has no feasible precomputed candidates")

    t0 = time.monotonic()
    best = math.inf
    calls = 0
    for _, a, _ in chosen:
        d = run_json([
            str(full_bin), "--wkt-file", field["local_wkt_path"],
            "--angle-deg", str(a),
        ])
        calls += 1
        best = min(best, float(d["complete_path_length_m"]))
    wall = time.monotonic() - t0

    return {
        "wall_seconds": wall,
        "bound_wall_seconds": 0.0,
        "selected_full_wall_seconds": wall,
        "full_calls": calls,
        "feasible_count": len(ranking),
        "infeasible_count": CANDIDATE_COUNT - len(ranking),
        "j_star_m": best,
    }


def q1q3(vals: Sequence[float]) -> Tuple[float, float]:
    return percentile(vals, 0.25), percentile(vals, 0.75)


def build_summary(
    runs: List[Dict[str, str]],
    selection: List[Dict[str, str]],
    repeats: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    success = [r for r in runs if r.get("status") == "SUCCESS"]
    detail: List[Dict[str, Any]] = []

    for field in selection:
        fid = field["field_id"]
        by_method = {}
        complete = True
        for method in METHODS:
            rr = [
                r for r in success
                if r["field_id"] == fid and r["method"] == method
            ]
            if len(rr) != repeats:
                complete = False
                break
            by_method[method] = rr
        if not complete:
            continue

        med = {
            m: statistics.median(float(r["wall_seconds"]) for r in rr)
            for m, rr in by_method.items()
        }
        q = {
            m: q1q3([float(r["wall_seconds"]) for r in rr])
            for m, rr in by_method.items()
        }
        cl = by_method["CLBOS_MST"]
        ex = by_method["EXHAUSTIVE"]
        tk = by_method["TOP10_LSW_PRECOMPUTED"]

        cl_exact = all(r["exact_to_authority"] == "true" for r in cl)
        ex_exact = all(r["exact_to_authority"] == "true" for r in ex)
        tk_exact = all(r["exact_to_authority"] == "true" for r in tk)

        cl_bound_med = statistics.median(float(r["bound_wall_seconds"]) for r in cl)
        cl_full_med = statistics.median(float(r["selected_full_wall_seconds"]) for r in cl)
        cl_calls_med = statistics.median(int(r["full_calls"]) for r in cl)

        detail.append({
            "field_id": fid,
            "family": field["family"],
            "area_m2": field["area_m2"],
            "repeat_count": repeats,
            "candidate_count": CANDIDATE_COUNT,
            "all_exhaustive_exact": ex_exact,
            "all_clbos_exact": cl_exact,
            "all_top10_exact": tk_exact,
            "median_exhaustive_seconds": med["EXHAUSTIVE"],
            "exhaustive_q1_seconds": q["EXHAUSTIVE"][0],
            "exhaustive_q3_seconds": q["EXHAUSTIVE"][1],
            "median_clbos_seconds": med["CLBOS_MST"],
            "clbos_q1_seconds": q["CLBOS_MST"][0],
            "clbos_q3_seconds": q["CLBOS_MST"][1],
            "median_top10_downstream_seconds": med["TOP10_LSW_PRECOMPUTED"],
            "top10_q1_seconds": q["TOP10_LSW_PRECOMPUTED"][0],
            "top10_q3_seconds": q["TOP10_LSW_PRECOMPUTED"][1],
            "clbos_speedup_vs_exhaustive": med["EXHAUSTIVE"] / med["CLBOS_MST"],
            "clbos_runtime_reduction_vs_exhaustive": 1.0 - med["CLBOS_MST"] / med["EXHAUSTIVE"],
            "clbos_certification_premium_ratio_vs_favorable_top10": med["CLBOS_MST"] / med["TOP10_LSW_PRECOMPUTED"],
            "clbos_certification_premium_seconds_vs_favorable_top10": med["CLBOS_MST"] - med["TOP10_LSW_PRECOMPUTED"],
            "median_clbos_bound_seconds": cl_bound_med,
            "median_clbos_selected_full_seconds": cl_full_med,
            "median_clbos_bound_fraction": cl_bound_med / med["CLBOS_MST"],
            "median_clbos_full_calls": cl_calls_med,
            "top10_timing_scope": "DOWNSTREAM_ONLY_PRECOMPUTED_LSW_RANKING_FAVORABLE_TO_TOP10",
        })

    pooled: Dict[str, Any] = {}
    if len(detail) == len(selection):
        per_rep_totals: Dict[Tuple[int, str], float] = defaultdict(float)
        per_rep_counts: Dict[Tuple[int, str], int] = defaultdict(int)
        for r in success:
            rep = int(r["repeat"])
            method = r["method"]
            if r["field_id"] in {f["field_id"] for f in selection}:
                per_rep_totals[(rep, method)] += float(r["wall_seconds"])
                per_rep_counts[(rep, method)] += 1

        totals = {}
        for method in METHODS:
            vv = [
                per_rep_totals[(rep, method)]
                for rep in range(1, repeats + 1)
                if per_rep_counts[(rep, method)] == len(selection)
            ]
            totals[method] = vv

        med_total = {
            m: statistics.median(v) for m, v in totals.items() if len(v) == repeats
        }

        speedups = [float(r["clbos_speedup_vs_exhaustive"]) for r in detail]
        reductions = [float(r["clbos_runtime_reduction_vs_exhaustive"]) for r in detail]
        premiums = [float(r["clbos_certification_premium_ratio_vs_favorable_top10"]) for r in detail]
        bound_fracs = [float(r["median_clbos_bound_fraction"]) for r in detail]
        calls = [float(r["median_clbos_full_calls"]) for r in detail]

        pooled = {
            "field_count": len(detail),
            "repeat_count": repeats,
            "candidate_count": CANDIDATE_COUNT,
            "clbos_exact_field_count": sum(bool(r["all_clbos_exact"]) for r in detail),
            "exhaustive_exact_field_count": sum(bool(r["all_exhaustive_exact"]) for r in detail),
            "top10_exact_field_count": sum(bool(r["all_top10_exact"]) for r in detail),
            "clbos_faster_than_exhaustive_field_count": sum(
                float(r["median_clbos_seconds"]) < float(r["median_exhaustive_seconds"])
                for r in detail
            ),
            "median_field_speedup_vs_exhaustive": statistics.median(speedups),
            "p25_field_speedup_vs_exhaustive": percentile(speedups, 0.25),
            "p75_field_speedup_vs_exhaustive": percentile(speedups, 0.75),
            "median_field_runtime_reduction_vs_exhaustive": statistics.median(reductions),
            "median_clbos_bound_fraction": statistics.median(bound_fracs),
            "median_clbos_full_calls": statistics.median(calls),
            "median_certification_premium_ratio_vs_favorable_top10": statistics.median(premiums),
            "aggregate_median_exhaustive_seconds_18_fields": med_total.get("EXHAUSTIVE"),
            "aggregate_median_clbos_seconds_18_fields": med_total.get("CLBOS_MST"),
            "aggregate_median_top10_downstream_seconds_18_fields": med_total.get("TOP10_LSW_PRECOMPUTED"),
            "aggregate_clbos_speedup_vs_exhaustive": (
                med_total["EXHAUSTIVE"] / med_total["CLBOS_MST"]
                if "EXHAUSTIVE" in med_total and "CLBOS_MST" in med_total else None
            ),
            "aggregate_clbos_runtime_reduction_vs_exhaustive": (
                1.0 - med_total["CLBOS_MST"] / med_total["EXHAUSTIVE"]
                if "EXHAUSTIVE" in med_total and "CLBOS_MST" in med_total else None
            ),
            "aggregate_certification_premium_ratio_vs_favorable_top10": (
                med_total["CLBOS_MST"] / med_total["TOP10_LSW_PRECOMPUTED"]
                if "CLBOS_MST" in med_total and "TOP10_LSW_PRECOMPUTED" in med_total else None
            ),
            "top10_timing_scope": "DOWNSTREAM_ONLY_PRECOMPUTED_LSW_RANKING_FAVORABLE_TO_TOP10",
        }
    return detail, pooled


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default="/path/to/agri_cross_module_canary")
    ap.add_argument("--repeats", type=int, default=REPEATS_DEFAULT)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    cache = Path.home() / ".cache/agri_cross_module_canary"
    mst_bin = cache / "Fields2Cover-build/agri_f2c_mst_probe"
    full_bin = cache / "Fields2Cover-build/agri_f2c_runner"

    selected90_path = root / "clbos01_heldout_topk/selected_heldout_fields.csv"
    prior9_path = root / "clbos01_resolution_scaling/selected_scaling_fields.csv"
    bound90_path = root / "clbos01_external_competitors_1deg_90/bound_1deg.csv"
    oracle90_path = root / "clbos01_external_competitors_1deg_90/field_results.csv"

    for p in (mst_bin, full_bin, selected90_path, prior9_path, bound90_path, oracle90_path):
        if not p.exists():
            raise RuntimeError(f"Missing required asset: {p}")

    head = git_head(cache / "Fields2Cover")
    if head != EXPECTED_F2C_HEAD:
        raise RuntimeError(
            f"Fields2Cover HEAD mismatch: expected {EXPECTED_F2C_HEAD}, got {head}"
        )

    selected90 = read_csv(selected90_path)
    prior9 = read_csv(prior9_path)
    selection = build_selection(selected90, prior9)

    # Validate local WKT assets before freeze.
    for f in selection:
        if not Path(f["local_wkt_path"]).exists():
            raise RuntimeError(f"Missing local WKT: {f['field_id']} -> {f['local_wkt_path']}")

    ranking, precomputed_infeas = load_bound_rankings(bound90_path)
    for f in selection:
        if f["field_id"] not in ranking or len(ranking[f["field_id"]]) < K:
            raise RuntimeError(f"Insufficient precomputed bound ranking: {f['field_id']}")

    oracle_rows = {
        r["field_id"]: r for r in read_csv(oracle90_path)
        if r.get("status") == "COMPLETE"
    }
    for f in selection:
        if f["field_id"] not in oracle_rows:
            raise RuntimeError(f"Missing authority oracle row: {f['field_id']}")

    if args.smoke:
        run_selection = selection[:1]
        repeats = 1
        base = root / "E3_REPRESENTATIVE_RUNTIME/smoke"
    else:
        run_selection = selection
        repeats = args.repeats
        if repeats != 5:
            raise RuntimeError("Formal E3 requires --repeats 5; use --smoke for preflight.")
        base = root / "E3_REPRESENTATIVE_RUNTIME"

    base.mkdir(parents=True, exist_ok=True)
    selection_out = base / "01_E3_SELECTION_FREEZE.csv"
    protocol_out = base / "02_E3_PROTOCOL_FREEZE.md"
    runs_out = base / "03_E3_RUNTIME_RUNS.csv"
    detail_out = base / "04_E3_FIELD_RUNTIME_SUMMARY.csv"
    report_out = base / "05_E3_SCIENTIFIC_REPORT.md"
    gate_out = base / "06_E3_GATE.json"
    system_out = base / "system_snapshot.txt"

    # Freeze selection before timing results.
    atomic_csv(selection_out, run_selection)

    script_sha = sha256_file(Path(__file__).resolve())
    protocol = f"""# E3 Protocol Freeze — Representative Runtime

- `TASK=CLBOS_E3_REPRESENTATIVE_RUNTIME`
- `FORMAL_RUN={str(not args.smoke).lower()}`
- `FIELD_COUNT={len(run_selection)}`
- `REPEATS={repeats}`
- `RESOLUTION=1deg`
- `CANDIDATE_COUNT=180`
- `FROZEN_K=10`
- `FIELDS2COVER_HEAD={head}`
- `SCRIPT_SHA256={script_sha}`

## Selection

Formal E3 selects 18 fields from the existing 90-field held-out metadata:
six per geometry family after excluding the nine fields previously used in
resolution-scaling timing. Within each family, fields are sorted by
`(area_m2, field_id)` and six equal-rank-bin midpoints are chosen.

No runtime, CLBOS Nfull, oracle rank, Top-K outcome, or downstream objective
enters the selection rule.

## Timing methods

1. `EXHAUSTIVE`: full planner over all 180 orientations.
2. `CLBOS_MST`: full 180-orientation MST bound sweep followed by certified
   selected Full calls; end-to-end Python driver wall time including subprocess overhead.
3. `TOP10_LSW_PRECOMPUTED`: frozen top ten orientations under the authoritative
   precomputed 1-degree SwathLength ranking; timing includes only downstream Full calls.

The third timing deliberately favors Top-10. Therefore CLBOS-vs-Top10 is a
conservative upper-bound estimate of the certificate premium, NOT an equal-scope
end-to-end runtime comparison.

## Runtime controls

- one MST + one Full warm-up per field;
- serial execution;
- deterministic counterbalanced method order across fields/repeats;
- timeout = 900 s per subprocess call;
- five repeats in the formal run;
- successful run keys are resumable and never silently overwritten;
- no method or parameter tuning after outcomes.
"""
    protocol_out.write_text(protocol, encoding="utf-8")

    system_lines = [
        "CLBOS E3 REPRESENTATIVE RUNTIME SYSTEM SNAPSHOT",
        f"platform={platform.platform()}",
        f"python={platform.python_version()}",
        f"processor={platform.processor()}",
        f"cpu_count={os.cpu_count()}",
        f"formal_run={not args.smoke}",
        f"field_count={len(run_selection)}",
        f"repeats={repeats}",
        "resolution=1deg",
        "candidate_count=180",
        "warmup=one MST probe + one Full call per field using a known feasible orientation",
        "parallel_execution=false",
        "timing_scope_EXHAUSTIVE=end-to-end Python driver wall clock including subprocess overhead",
        "timing_scope_CLBOS_MST=end-to-end Python driver wall clock including subprocess overhead",
        "timing_scope_TOP10=downstream-only Full calls from precomputed SwathLength ranking; favorable to Top10",
        "clbos_implementation=current conservative implementation; selected Full calls recompute upstream",
        f"Fields2Cover_HEAD={head}",
        f"MST_BIN_SHA256={sha256_file(mst_bin)}",
        f"FULL_BIN_SHA256={sha256_file(full_bin)}",
        f"SCRIPT_SHA256={script_sha}",
    ]
    system_out.write_text("\n".join(system_lines) + "\n", encoding="utf-8")

    run_fields = [
        "field_id", "family", "area_m2", "repeat", "method", "order_in_repeat",
        "status", "wall_seconds", "bound_wall_seconds", "selected_full_wall_seconds",
        "full_calls", "feasible_count", "infeasible_count", "j_star_m",
        "authority_oracle_j_m", "exact_to_authority", "error",
    ]
    existing = read_csv(runs_out)
    done = {
        (r["field_id"], int(r["repeat"]), r["method"])
        for r in existing if r.get("status") == "SUCCESS"
    }

    for field_idx, field in enumerate(run_selection):
        fid = field["field_id"]
        print(f"WARMUP {field_idx+1}/{len(run_selection)} {fid}", flush=True)
        warmup(field, ranking[fid], mst_bin, full_bin)
        authority_j = float(oracle_rows[fid]["oracle_j_star_m"])

        for rep in range(1, repeats + 1):
            order = PERMUTATIONS[(field_idx + rep - 1) % len(PERMUTATIONS)]
            for order_idx, method in enumerate(order, 1):
                key = (fid, rep, method)
                if key in done:
                    print("SKIP", key, flush=True)
                    continue

                print(
                    f"RUN field={field_idx+1}/{len(run_selection)} "
                    f"{fid} rep={rep}/{repeats} method={method} order={order_idx}",
                    flush=True,
                )
                try:
                    if method == "EXHAUSTIVE":
                        res = run_exhaustive(field, full_bin)
                    elif method == "CLBOS_MST":
                        res = run_clbos(field, mst_bin, full_bin)
                    elif method == "TOP10_LSW_PRECOMPUTED":
                        res = run_top10_precomputed(field, ranking[fid], full_bin)
                    else:
                        raise RuntimeError(f"Unknown method: {method}")

                    exact = abs(float(res["j_star_m"]) - authority_j) <= EXACT_TOL_M
                    row = {
                        "field_id": fid,
                        "family": field["family"],
                        "area_m2": field["area_m2"],
                        "repeat": rep,
                        "method": method,
                        "order_in_repeat": order_idx,
                        "status": "SUCCESS",
                        "wall_seconds": f"{res['wall_seconds']:.9f}",
                        "bound_wall_seconds": f"{res['bound_wall_seconds']:.9f}",
                        "selected_full_wall_seconds": f"{res['selected_full_wall_seconds']:.9f}",
                        "full_calls": res["full_calls"],
                        "feasible_count": res["feasible_count"],
                        "infeasible_count": res["infeasible_count"],
                        "j_star_m": f"{res['j_star_m']:.12f}",
                        "authority_oracle_j_m": f"{authority_j:.12f}",
                        "exact_to_authority": str(exact).lower(),
                        "error": "",
                    }
                except Exception as e:
                    row = {
                        "field_id": fid,
                        "family": field["family"],
                        "area_m2": field["area_m2"],
                        "repeat": rep,
                        "method": method,
                        "order_in_repeat": order_idx,
                        "status": "FAILED",
                        "wall_seconds": "",
                        "bound_wall_seconds": "",
                        "selected_full_wall_seconds": "",
                        "full_calls": "",
                        "feasible_count": "",
                        "infeasible_count": "",
                        "j_star_m": "",
                        "authority_oracle_j_m": f"{authority_j:.12f}",
                        "exact_to_authority": "false",
                        "error": repr(e),
                    }

                append_csv(runs_out, run_fields, row)
                if row["status"] != "SUCCESS":
                    raise RuntimeError(row["error"])
                if method in {"EXHAUSTIVE", "CLBOS_MST"} and row["exact_to_authority"] != "true":
                    raise RuntimeError(
                        f"{method} did not match authority oracle for {fid}: "
                        f"{row['j_star_m']} vs {row['authority_oracle_j_m']}"
                    )
                done.add(key)

    all_runs = read_csv(runs_out)
    detail, pooled = build_summary(all_runs, run_selection, repeats)
    atomic_csv(detail_out, detail)

    formal_complete = len(detail) == len(run_selection)
    if formal_complete:
        clbos_exact = int(pooled["clbos_exact_field_count"])
        agg_speedup = pooled["aggregate_clbos_speedup_vs_exhaustive"]
        faster_count = int(pooled["clbos_faster_than_exhaustive_field_count"])
        if clbos_exact != len(run_selection):
            classification = "CERTIFICATE_RUNTIME_ANOMALY"
        elif agg_speedup is not None and agg_speedup > 1.0:
            classification = "REPRESENTATIVE_RUNTIME_BENEFIT_SUPPORTED"
        else:
            classification = "CERTIFIED_SEARCH_NO_AGGREGATE_RUNTIME_BENEFIT"
    else:
        classification = "INCOMPLETE"

    lines = [
        "# E3 Scientific Report — Representative Runtime",
        "",
        "## Scope",
        "",
        f"- Formal run: **{not args.smoke}**",
        f"- Fields: **{len(run_selection)}**",
        f"- Repeats: **{repeats}**",
        "- Resolution: **1° (180 candidate orientations)**",
        "- Methods: Exhaustive, CLBOS-MST, frozen Top-10.",
        "- Exhaustive and CLBOS timing are end-to-end Python-driver wall clock including subprocess overhead.",
        "- Top-10 timing is downstream-only using a precomputed frozen SwathLength ranking and therefore intentionally favors Top-10.",
        "",
    ]

    if formal_complete:
        lines += [
            "## Aggregate results",
            "",
            f"- CLBOS exact fields: **{pooled['clbos_exact_field_count']}/{pooled['field_count']}**.",
            f"- Exhaustive exact fields: **{pooled['exhaustive_exact_field_count']}/{pooled['field_count']}**.",
            f"- Frozen Top-10 exact fields: **{pooled['top10_exact_field_count']}/{pooled['field_count']}**.",
            f"- CLBOS faster than exhaustive: **{pooled['clbos_faster_than_exhaustive_field_count']}/{pooled['field_count']} fields**.",
            f"- Median field-level CLBOS speedup vs exhaustive: **{pooled['median_field_speedup_vs_exhaustive']:.4f}×**.",
            f"- Median field-level runtime reduction vs exhaustive: **{100*pooled['median_field_runtime_reduction_vs_exhaustive']:.2f}%**.",
            f"- Aggregate 18-field median-repeat exhaustive wall time: **{pooled['aggregate_median_exhaustive_seconds_18_fields']:.3f} s**.",
            f"- Aggregate 18-field median-repeat CLBOS wall time: **{pooled['aggregate_median_clbos_seconds_18_fields']:.3f} s**.",
            f"- Aggregate CLBOS speedup vs exhaustive: **{pooled['aggregate_clbos_speedup_vs_exhaustive']:.4f}×**.",
            f"- Aggregate runtime reduction vs exhaustive: **{100*pooled['aggregate_clbos_runtime_reduction_vs_exhaustive']:.2f}%**.",
            f"- Median CLBOS bound-acquisition fraction: **{100*pooled['median_clbos_bound_fraction']:.2f}%**.",
            f"- Median CLBOS Full calls per field: **{pooled['median_clbos_full_calls']}**.",
            "",
            "## Certification premium against frozen Top-10",
            "",
            f"- Aggregate Top-10 downstream-only median-repeat wall time: **{pooled['aggregate_median_top10_downstream_seconds_18_fields']:.3f} s**.",
            f"- Aggregate CLBOS / favorable-Top10 wall-time ratio: **{pooled['aggregate_certification_premium_ratio_vs_favorable_top10']:.4f}×**.",
            f"- Median field-level CLBOS / favorable-Top10 ratio: **{pooled['median_certification_premium_ratio_vs_favorable_top10']:.4f}×**.",
            "",
            "This is deliberately a conservative estimate of the certification premium because Top-10 ranking acquisition is omitted from its timer.",
            "",
            "## Scientific classification",
            "",
            f"`E3_FINAL_CLASSIFICATION={classification}`",
        ]
    else:
        lines += [
            "## Scientific classification",
            "",
            "`E3_FINAL_CLASSIFICATION=INCOMPLETE`",
        ]

    report_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    failure_rows = [r for r in all_runs if r.get("status") == "FAILED"]
    gate = {
        "TASK_STATUS": "COMPLETE" if formal_complete else "INCOMPLETE",
        "FORMAL_RUN": not args.smoke,
        "DEPENDENCY_CLOSURE_PASS": True,
        "FIELDS2COVER_HEAD": head,
        "EXPECTED_FIELDS2COVER_HEAD": EXPECTED_F2C_HEAD,
        "FIELD_COUNT": len(run_selection),
        "REPEAT_COUNT": repeats,
        "RESOLUTION_DEG": 1.0,
        "CANDIDATE_COUNT": 180,
        "FROZEN_K": 10,
        "SELECTION_USES_RUNTIME_OUTCOMES": False,
        "PRIOR_TIMING_FIELDS_EXCLUDED": True,
        "METHOD_MODIFIED": False,
        "MANUSCRIPT_MODIFIED": False,
        "PUBLIC_RELEASE_MODIFIED": False,
        "PARALLEL_EXECUTION": False,
        "TIMEOUT_SECONDS_PER_SUBPROCESS": TIMEOUT,
        "TIMING_SCOPE_EXHAUSTIVE": "END_TO_END_PYTHON_DRIVER_INCLUDING_SUBPROCESS_OVERHEAD",
        "TIMING_SCOPE_CLBOS": "END_TO_END_PYTHON_DRIVER_INCLUDING_SUBPROCESS_OVERHEAD",
        "TIMING_SCOPE_TOP10": "DOWNSTREAM_ONLY_PRECOMPUTED_LSW_RANKING_FAVORABLE_TO_TOP10",
        "FAILED_RUN_COUNT": len(failure_rows),
        "COMPLETE_FIELD_SUMMARY_COUNT": len(detail),
        "POOLED": pooled,
        "E3_FINAL_CLASSIFICATION": classification,
        "OUTPUT_SHA256": {
            "01_E3_SELECTION_FREEZE.csv": sha256_file(selection_out),
            "02_E3_PROTOCOL_FREEZE.md": sha256_file(protocol_out),
            "03_E3_RUNTIME_RUNS.csv": sha256_file(runs_out),
            "04_E3_FIELD_RUNTIME_SUMMARY.csv": sha256_file(detail_out),
            "05_E3_SCIENTIFIC_REPORT.md": sha256_file(report_out),
        },
    }
    with gate_out.open("w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False, indent=2)

    print("TASK_STATUS=" + gate["TASK_STATUS"])
    print(f"FORMAL_RUN={str(not args.smoke).lower()}")
    print(f"FIELD_COUNT={len(run_selection)}")
    print(f"REPEAT_COUNT={repeats}")
    print(f"FAILED_RUN_COUNT={len(failure_rows)}")
    print(f"COMPLETE_FIELD_SUMMARY_COUNT={len(detail)}")
    if pooled:
        print(f"CLBOS_EXACT_FIELD_COUNT={pooled['clbos_exact_field_count']}")
        print(f"TOP10_EXACT_FIELD_COUNT={pooled['top10_exact_field_count']}")
        print(f"CLBOS_FASTER_THAN_EXHAUSTIVE_FIELD_COUNT={pooled['clbos_faster_than_exhaustive_field_count']}")
        print(f"MEDIAN_FIELD_SPEEDUP_VS_EXHAUSTIVE={pooled['median_field_speedup_vs_exhaustive']}")
        print(f"AGGREGATE_SPEEDUP_VS_EXHAUSTIVE={pooled['aggregate_clbos_speedup_vs_exhaustive']}")
        print(f"AGGREGATE_RUNTIME_REDUCTION_VS_EXHAUSTIVE={pooled['aggregate_clbos_runtime_reduction_vs_exhaustive']}")
        print(f"MEDIAN_CLBOS_BOUND_FRACTION={pooled['median_clbos_bound_fraction']}")
        print(f"AGGREGATE_CERTIFICATION_PREMIUM_RATIO_VS_FAVORABLE_TOP10={pooled['aggregate_certification_premium_ratio_vs_favorable_top10']}")
    print(f"E3_FINAL_CLASSIFICATION={classification}")
    print("NEW_METHOD_DEVELOPMENT=false")
    print("MANUSCRIPT_MODIFIED=false")
    print("EXPECTED_GPT_RETURN_FILE_COUNT=6")
    for p in (selection_out, protocol_out, runs_out, detail_out, report_out, gate_out):
        print(p)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
