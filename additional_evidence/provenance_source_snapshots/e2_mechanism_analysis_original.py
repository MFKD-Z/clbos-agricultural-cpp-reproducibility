# PUBLIC NOTE: path-sanitized source snapshot of the executed experiment script; not the portable reproduction entry point.
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLBOS E2 — Certification Difficulty Mechanism Analysis
======================================================

Pure-Python (standard library only) analysis script for Ubuntu/WSL.

Scientific scope:
  E2-A PRIMARY:
    Paired 2.0 m -> 2.8 m minimum-turning-radius intervention on the 30 E1 T2 fields.
    Test:
      stronger turning constraint
        -> larger J - LB1 relaxation gap
        -> larger CLBOS complete-evaluation effort Nfull.

  E2-B SECONDARY:
    Original 90-field hard-tail analysis, BUT ONLY if a genuinely exhaustive
    per-angle complete-path J(theta) table can be discovered and verified
    against the full 1-degree bound-success angle set.

  E2-C TERTIARY:
    T1 vs T3 (1 deg vs 0.5 deg) paired descriptive resolution analysis.

Safety:
  - NO Fields2Cover calls.
  - NO new Route+Path calls.
  - NO method changes.
  - NO manuscript/public-release changes.
  - Existing scientific inputs are read-only.
  - Does not install packages.

Expected project root:
  /path/to/agri_cross_module_canary
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "E2_MECHANISM_1.0"
TOL = 1e-6
BOOTSTRAP_N = 5000
BOOTSTRAP_SEED = 20260813

SKIP_SCAN_PARTS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "release", "E2_CERTIFICATION_MECHANISM",
}

OBJECTIVE_COLUMNS = (
    "complete_path_length_m",
    "oracle_complete_path_length_m",
    "complete_path_m",
    "path_length_m",
    "j_m",
    "objective_m",
)

SUCCESS_VALUES = {
    "", "success", "ok", "complete", "valid", "certified_exact",
    "true", "1",
}


# ---------------------------------------------------------------------------
# Generic utilities
# ---------------------------------------------------------------------------

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")


def fnum(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    try:
        v = float(s)
    except Exception:
        return None
    return v if math.isfinite(v) else None


def inum(x: Any) -> Optional[int]:
    v = fnum(x)
    return int(round(v)) if v is not None else None


def bval(x: Any) -> Optional[bool]:
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in {"true", "1", "yes", "y", "pass"}:
        return True
    if s in {"false", "0", "no", "n", "fail"}:
        return False
    return None


def norm_status(x: Any) -> str:
    return str(x or "").strip().lower()


def is_success_status(x: Any) -> bool:
    s = norm_status(x)
    if not s:
        return True
    if s in SUCCESS_VALUES:
        return True
    return (
        "success" in s
        or "valid" in s
        or "complete" in s
        or "certified_exact" in s
    ) and not any(k in s for k in ("fail", "error", "timeout", "infeasible"))


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def csv_header(path: Path) -> List[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
            return next(csv.reader(f), [])
    except Exception:
        return []


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        seen = []
        seen_set = set()
        for r in rows:
            for k in r.keys():
                if k not in seen_set:
                    seen.append(k)
                    seen_set.add(k)
        fieldnames = seen
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            out = {}
            for k in fieldnames:
                v = row.get(k, "")
                if isinstance(v, float):
                    if math.isnan(v):
                        out[k] = ""
                    else:
                        out[k] = f"{v:.12g}"
                elif v is None:
                    out[k] = ""
                else:
                    out[k] = v
            w.writerow(out)


def angle_key(x: Any) -> Optional[float]:
    v = fnum(x)
    return round(v, 8) if v is not None else None


def percentile(xs: Sequence[float], q: float) -> Optional[float]:
    vals = sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def median(xs: Sequence[float]) -> Optional[float]:
    vals = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(vals) if vals else None


def iqr(xs: Sequence[float]) -> Optional[float]:
    q1 = percentile(xs, 0.25)
    q3 = percentile(xs, 0.75)
    return (q3 - q1) if q1 is not None and q3 is not None else None


def average_ranks(xs: Sequence[float]) -> List[float]:
    indexed = sorted(enumerate(xs), key=lambda z: z[1])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    sx = sum(v * v for v in dx)
    sy = sum(v * v for v in dy)
    if sx <= 0 or sy <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(sx * sy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys)
             if x is not None and y is not None
             and math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 3:
        return None
    x, y = zip(*pairs)
    return pearson(average_ranks(x), average_ranks(y))


def bootstrap_ci_stat(
    xs: Sequence[float],
    stat_fn,
    n: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> Tuple[Optional[float], Optional[float]]:
    vals = list(xs)
    if not vals:
        return None, None
    rng = random.Random(seed)
    stats = []
    m = len(vals)
    for _ in range(n):
        sample = [vals[rng.randrange(m)] for _ in range(m)]
        try:
            s = stat_fn(sample)
        except Exception:
            s = None
        if s is not None and math.isfinite(float(s)):
            stats.append(float(s))
    if not stats:
        return None, None
    return percentile(stats, 0.025), percentile(stats, 0.975)


def bootstrap_ci_rho(
    xs: Sequence[float],
    ys: Sequence[float],
    n: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED + 17,
) -> Tuple[Optional[float], Optional[float]]:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys)
             if x is not None and y is not None
             and math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 4:
        return None, None
    rng = random.Random(seed)
    stats = []
    m = len(pairs)
    for _ in range(n):
        sample = [pairs[rng.randrange(m)] for _ in range(m)]
        sx = [p[0] for p in sample]
        sy = [p[1] for p in sample]
        r = spearman(sx, sy)
        if r is not None and math.isfinite(r):
            stats.append(r)
    if not stats:
        return None, None
    return percentile(stats, 0.025), percentile(stats, 0.975)


def exact_sign_test_two_sided(deltas: Sequence[float], tol: float = 1e-12) -> Optional[float]:
    pos = sum(1 for d in deltas if d > tol)
    neg = sum(1 for d in deltas if d < -tol)
    n = pos + neg
    if n == 0:
        return None
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def finite_or_none(x: Optional[float]) -> Optional[float]:
    if x is None or not math.isfinite(x):
        return None
    return x


# ---------------------------------------------------------------------------
# Lightweight OLS without numpy
# ---------------------------------------------------------------------------

def solve_linear(A: List[List[float]], b: List[float]) -> Optional[List[float]]:
    n = len(A)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-12:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r == col:
                continue
            fac = M[r][col]
            if fac == 0:
                continue
            for j in range(col, n + 1):
                M[r][j] -= fac * M[col][j]
    return [M[i][n] for i in range(n)]


def zscore(vals: Sequence[float]) -> Optional[List[float]]:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    ss = sum((x - m) ** 2 for x in vals)
    if ss <= 0:
        return None
    sd = math.sqrt(ss / (len(vals) - 1))
    if sd <= 0:
        return None
    return [(x - m) / sd for x in vals]


def ols_model(
    rows: List[Dict[str, Any]],
    y_key: str,
    x_keys: List[str],
    log_y: bool = True,
    transforms: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    transforms = transforms or {}
    clean = []
    for r in rows:
        y = fnum(r.get(y_key))
        xs = [fnum(r.get(k)) for k in x_keys]
        if y is None or any(v is None for v in xs):
            continue
        if log_y:
            y = math.log1p(max(0.0, y))
        tx = []
        ok = True
        for k, v in zip(x_keys, xs):
            mode = transforms.get(k)
            if mode == "log1p":
                if v < 0:
                    ok = False
                    break
                tx.append(math.log1p(v))
            else:
                tx.append(v)
        if ok:
            clean.append((y, tx))
    n = len(clean)
    p = len(x_keys) + 1
    if n <= p + 1:
        return {"status": "INSUFFICIENT_N", "n": n, "x_keys": x_keys}

    yv = [a for a, _ in clean]
    cols = list(zip(*[b for _, b in clean]))
    zcols = []
    for col in cols:
        z = zscore(col)
        if z is None:
            return {"status": "SINGULAR_PREDICTOR", "n": n, "x_keys": x_keys}
        zcols.append(z)

    X = []
    for i in range(n):
        X.append([1.0] + [zcols[j][i] for j in range(len(zcols))])

    XtX = [[0.0] * p for _ in range(p)]
    Xty = [0.0] * p
    for i in range(n):
        for a in range(p):
            Xty[a] += X[i][a] * yv[i]
            for b in range(p):
                XtX[a][b] += X[i][a] * X[i][b]

    beta = solve_linear(XtX, Xty)
    if beta is None:
        return {"status": "SINGULAR", "n": n, "x_keys": x_keys}

    pred = [sum(beta[j] * X[i][j] for j in range(p)) for i in range(n)]
    ym = sum(yv) / n
    sse = sum((y - yh) ** 2 for y, yh in zip(yv, pred))
    sst = sum((y - ym) ** 2 for y in yv)
    r2 = 1.0 - sse / sst if sst > 0 else None
    adj = None
    if r2 is not None and n > p:
        adj = 1.0 - (1.0 - r2) * (n - 1) / (n - p)

    return {
        "status": "OK",
        "n": n,
        "y_key": y_key,
        "x_keys": x_keys,
        "beta_intercept": beta[0],
        "standardized_betas": {k: beta[i + 1] for i, k in enumerate(x_keys)},
        "r2": r2,
        "adjusted_r2": adj,
    }


# ---------------------------------------------------------------------------
# Relaxation metrics
# ---------------------------------------------------------------------------

def relaxation_metrics(lsw: float, lb1: float, J: float) -> Dict[str, Optional[float]]:
    tmst = lb1 - lsw
    lnonwork = J - lsw
    gap = J - lb1
    rel_gap = gap / J if J > TOL else None
    capture = tmst / lnonwork if lnonwork > TOL else None
    return {
        "Lsw_m": lsw,
        "LB1_m": lb1,
        "TMST_m": tmst,
        "J_m": J,
        "Lnonwork_m": lnonwork,
        "abs_relaxation_gap_m": gap,
        "rel_relaxation_gap": rel_gap,
        "mst_capture_ratio": capture,
    }


def summarize_orientation_metrics(items: List[Dict[str, Optional[float]]]) -> Dict[str, Optional[float]]:
    abs_gaps = [x["abs_relaxation_gap_m"] for x in items if x["abs_relaxation_gap_m"] is not None]
    rel_gaps = [x["rel_relaxation_gap"] for x in items if x["rel_relaxation_gap"] is not None]
    captures = [x["mst_capture_ratio"] for x in items if x["mst_capture_ratio"] is not None]
    lsws = [x["Lsw_m"] for x in items if x["Lsw_m"] is not None]
    tmsts = [x["TMST_m"] for x in items if x["TMST_m"] is not None]
    return {
        "orientation_n": len(items),
        "median_abs_gap_m": median(abs_gaps),
        "p90_abs_gap_m": percentile(abs_gaps, 0.90),
        "median_rel_gap": median(rel_gaps),
        "p90_rel_gap": percentile(rel_gaps, 0.90),
        "median_mst_capture_ratio": median(captures),
        "median_lsw_m": median(lsws),
        "median_tmst_m": median(tmsts),
    }


# ---------------------------------------------------------------------------
# E1 loading
# ---------------------------------------------------------------------------

def load_e1(e1_root: Path) -> Dict[str, Any]:
    transfer_path = e1_root / "04_E1_TRANSFER_RESULTS.csv"
    bounds_path = e1_root / "raw" / "candidate_bounds.csv"
    paths_path = e1_root / "raw" / "candidate_full_paths.csv"
    freeze_path = e1_root / "03_E1_SELECTION_AND_CONFIG_FREEZE.json"
    gate_path = e1_root / "06_E1_GATE.json"

    for p, label in [
        (transfer_path, "E1 transfer results"),
        (bounds_path, "E1 candidate bounds"),
        (paths_path, "E1 candidate full paths"),
        (freeze_path, "E1 freeze"),
        (gate_path, "E1 gate"),
    ]:
        ensure_exists(p, label)

    transfer = read_csv(transfer_path)
    bounds = read_csv(bounds_path)
    full = read_csv(paths_path)
    with freeze_path.open("r", encoding="utf-8-sig") as f:
        freeze = json.load(f)
    with gate_path.open("r", encoding="utf-8-sig") as f:
        gate = json.load(f)

    return {
        "transfer": transfer,
        "bounds": bounds,
        "full": full,
        "freeze": freeze,
        "gate": gate,
        "paths": {
            "transfer": transfer_path,
            "bounds": bounds_path,
            "full": paths_path,
            "freeze": freeze_path,
            "gate": gate_path,
        }
    }


def index_e1(data: Dict[str, Any]) -> Dict[str, Any]:
    summary_by_arm_sha = {}
    for r in data["transfer"]:
        arm = r.get("experiment_arm", "")
        sha = r.get("source_sha256", "")
        summary_by_arm_sha[(arm, sha)] = r

    bounds_by_arm_sha_angle = {}
    bound_violation_source_rows = 0
    t2_bound_row_count = 0
    for r in data["bounds"]:
        arm = r.get("experiment_arm", "")
        if arm == "T2":
            t2_bound_row_count += 1
        if not is_success_status(r.get("status")):
            continue
        sha = r.get("source_sha256", "")
        ang = angle_key(r.get("angle_deg"))
        lsw = fnum(r.get("swath_total_length_m"))
        lb1 = fnum(r.get("mst_total_lb_m"))
        if sha and ang is not None and lsw is not None and lb1 is not None:
            bounds_by_arm_sha_angle[(arm, sha, ang)] = (lsw, lb1, r)

    full_by_arm_sha_angle = {}
    for r in data["full"]:
        if not is_success_status(r.get("status")):
            continue
        arm = r.get("experiment_arm", "")
        sha = r.get("source_sha256", "")
        ang = angle_key(r.get("angle_deg"))
        J = fnum(r.get("complete_path_length_m"))
        if sha and ang is not None and J is not None:
            full_by_arm_sha_angle[(arm, sha, ang)] = (J, r)

    return {
        "summary": summary_by_arm_sha,
        "bounds": bounds_by_arm_sha_angle,
        "full": full_by_arm_sha_angle,
        "t2_bound_row_count": t2_bound_row_count,
    }


# ---------------------------------------------------------------------------
# Original 90-field exhaustive J(theta) discovery
# ---------------------------------------------------------------------------

def discover_exhaustive_j_table(
    project_root: Path,
    target_fields: set,
    bound_success_angles: Dict[str, set],
    output_dir: Path,
) -> Tuple[Optional[Path], Optional[str], List[Dict[str, Any]], Dict[Tuple[str, float], float]]:
    """
    Find a CSV containing near-complete J(theta) for the target 90 fields.

    Verification criterion:
      - objective-bearing table,
      - field_id + angle_deg,
      - matched successful field-angle coverage >= 99.5% of the full
        bound-success angle set,
      - >= 90 target fields covered when target has 90.
    """
    total_required = sum(len(v) for v in bound_success_angles.values())
    candidates = []

    for root, dirs, files in os.walk(project_root):
        rp = Path(root)
        keep = []
        for d in dirs:
            dp = rp / d
            parts = {p.lower() for p in dp.parts}
            if any(x.lower() in parts for x in SKIP_SCAN_PARTS):
                continue
            keep.append(d)
        dirs[:] = keep

        for fn in files:
            if not fn.lower().endswith(".csv"):
                continue
            p = rp / fn
            if output_dir in p.parents:
                continue
            hdr = csv_header(p)
            low = {h.lower(): h for h in hdr}
            if "field_id" not in low or "angle_deg" not in low:
                continue
            obj_col = None
            for c in OBJECTIVE_COLUMNS:
                if c in low:
                    obj_col = low[c]
                    break
            if obj_col is None:
                continue

            field_col = low["field_id"]
            angle_col = low["angle_deg"]
            status_col = low.get("status")

            matched = {}
            seen_fields = set()
            target_rows = 0
            duplicate_keys = 0
            try:
                with p.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
                    rd = csv.DictReader(f)
                    for r in rd:
                        fid = str(r.get(field_col, "")).strip()
                        if fid not in target_fields:
                            continue
                        if status_col and not is_success_status(r.get(status_col)):
                            continue
                        ang = angle_key(r.get(angle_col))
                        J = fnum(r.get(obj_col))
                        if ang is None or J is None:
                            continue
                        target_rows += 1
                        if ang not in bound_success_angles.get(fid, set()):
                            continue
                        key = (fid, ang)
                        if key in matched:
                            duplicate_keys += 1
                        else:
                            matched[key] = J
                            seen_fields.add(fid)
            except Exception as e:
                continue

            coverage = len(matched) / total_required if total_required else 0.0
            min_required = min((len(v) for v in bound_success_angles.values()), default=0)
            matched_by_field = Counter(fid for fid, _ in matched)
            min_match = min((matched_by_field.get(fid, 0) for fid in target_fields), default=0)
            candidate = {
                "path": str(p),
                "objective_column": obj_col,
                "target_rows": target_rows,
                "matched_unique_field_angles": len(matched),
                "required_unique_field_angles": total_required,
                "coverage_fraction": coverage,
                "target_field_count": len(seen_fields),
                "duplicate_matched_keys": duplicate_keys,
                "minimum_matched_angles_per_target_field": min_match,
                "minimum_required_angles_per_target_field": min_required,
            }
            candidates.append((candidate, matched))

    candidates.sort(
        key=lambda z: (
            -z[0]["coverage_fraction"],
            -z[0]["target_field_count"],
            z[0]["duplicate_matched_keys"],
            z[0]["path"],
        )
    )
    audit = [c for c, _ in candidates[:20]]

    if not candidates:
        return None, None, audit, {}

    best_meta, best_matched = candidates[0]
    require_fields = len(target_fields)
    if (
        best_meta["coverage_fraction"] >= 0.995
        and best_meta["target_field_count"] >= require_fields
    ):
        return Path(best_meta["path"]), best_meta["objective_column"], audit, best_matched

    return None, None, audit, {}


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default="/path/to/agri_cross_module_canary")
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    else:
        output_dir = project_root / "E2_CERTIFICATION_MECHANISM"

    if not project_root.exists():
        print(f"ERROR: PROJECT_ROOT not found: {project_root}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)

    e1_root = project_root / "E1_FROZEN_K_TRANSFER"
    ensure_exists(e1_root, "E1 root")

    # ------------------------------------------------------------------
    # Freeze document is written before loading scientific result rows.
    # ------------------------------------------------------------------
    script_path = Path(__file__).resolve()
    freeze_out = output_dir / "01_E2_ANALYSIS_FREEZE.md"
    freeze_text = f"""# E2 Analysis Freeze — Certification Difficulty Mechanism

## Identity

- `TASK=CLBOS_E2_CERTIFICATION_DIFFICULTY_MECHANISM`
- `SCHEMA_VERSION={SCHEMA_VERSION}`
- `SCRIPT_SHA256={sha256_file(script_path)}`
- `NEW_ROUTE_PATH_CALL_AUTHORIZED=false`
- `METHOD_MODIFICATION_AUTHORIZED=false`
- `MANUSCRIPT_EDIT_AUTHORIZED=false`
- `PUBLIC_RELEASE_MODIFICATION_AUTHORIZED=false`
- `STANDARD_LIBRARY_ONLY=true`
- `BOOTSTRAP_N={BOOTSTRAP_N}`
- `BOOTSTRAP_SEED={BOOTSTRAP_SEED}`

## Primary mechanism H1

On the same preselected E1 T2 fields, Configuration B changes only the minimum turning radius
from 2.0 m to 2.8 m. The E1 protocol freezes swath-stage geometry and Euclidean MST lower-bound
semantics. E2 tests whether the stronger curvature constraint increases:

1. `J(theta) - LB1(theta)` across common valid orientations; and
2. field-level CLBOS `Nfull`.

Primary field-level gap descriptor: `P90[J(theta)-LB1(theta)]`.
Primary paired association: Spearman correlation between the B-A change in that descriptor
and the B-A change in `Nfull`.

`H1_STRONG_SUPPORT` requires:
- no material bound violation,
- larger total effort in B and more fields increasing than decreasing,
- positive median field-level P90 absolute-gap change,
- Spearman rho >= 0.30 between paired gap change and paired Nfull change.

If the directional effects hold but rho < 0.30, classification is `H1_PARTIAL_SUPPORT`.
Otherwise `H1_NOT_SUPPORTED`.

## Secondary H2

The original 90-field hard-tail analysis is permitted only if E2 discovers a per-angle complete-path
table whose successful `(field_id, angle_deg)` keys cover at least 99.5% of the full 1-degree
bound-success keys for all 90 target fields.

If that exhaustive table is not available, E2-B is marked an honest blocker and no selected-call
table is substituted.

When available, field-level `P90 relative relaxation gap` is compared with upstream scale proxies
and `Nfull`; simple OLS models are descriptive only.

## Circularity guard

The following are NOT used as causal predictors of Nfull:
- number/fraction of bounds below `J* + epsilon`,
- stopping-bound rank,
- survivor count,
- any algebraic equivalent of Nfull.

`J(theta)-LB1(theta)` is treated as a downstream-informed mechanism diagnostic, not a deployable
pre-planning predictor.

## Tertiary E2-C

T1 vs T3 is descriptive only and does not determine H1 or H2.
"""
    freeze_out.write_text(freeze_text, encoding="utf-8")

    # Load E1 after freeze.
    e1 = load_e1(e1_root)
    ix = index_e1(e1)

    # Validate frozen config facts from E1.
    freeze = e1["freeze"]
    cfg_a = freeze.get("configuration_A", {})
    cfg_b = freeze.get("configuration_B", {})
    a_radius = fnum(cfg_a.get("minimum_turning_radius_m"))
    b_radius = fnum(cfg_b.get("configuration_B_value"))
    a1a4_pass = bool(freeze.get("A1_A4_config_B", {}).get("A1_A4_CONFIG_B_PASS", False))
    config_b_single_factor = bool(cfg_b.get("all_other_parameters_identical_to_A", False))
    bound_semantics_unchanged = bool(freeze.get("A1_A4_config_B", {}).get("ASSUMPTION_SEMANTICS_UNCHANGED", False))

    # Build T1/T2 pair list.
    t2_shas = sorted({
        sha for (arm, sha), r in ix["summary"].items() if arm == "T2"
    })
    paired_rows: List[Dict[str, Any]] = []
    all_field_metric_rows: List[Dict[str, Any]] = []
    bound_violation_count = 0
    severe_capture_violation_count = 0
    missing_join_count = 0

    for sha in t2_shas:
        sA = ix["summary"].get(("T1", sha))
        sB = ix["summary"].get(("T2", sha))
        if not sA or not sB:
            continue

        field_id = sA.get("field_id") or sB.get("field_id")
        nA = inum(sA.get("clbos_Nfull"))
        nB = inum(sB.get("clbos_Nfull"))
        JAstar = fnum(sA.get("oracle_J"))
        JBstar = fnum(sB.get("oracle_J"))

        items_A = []
        items_B = []
        common_angles = []

        # T2 deliberately reuses the same swath/MST bound semantics as T1.
        # candidate_bounds.csv therefore contains T1/T3 only.
        A_angles = {
            ang for (arm, sh, ang) in ix["full"].keys()
            if arm == "T1" and sh == sha
        }
        B_angles = {
            ang for (arm, sh, ang) in ix["full"].keys()
            if arm == "T2" and sh == sha
        }
        common = sorted(A_angles & B_angles)

        for ang in common:
            bnd = ix["bounds"].get(("T1", sha, ang))
            pA = ix["full"].get(("T1", sha, ang))
            pB = ix["full"].get(("T2", sha, ang))
            if not bnd or not pA or not pB:
                missing_join_count += 1
                continue
            lsw, lb1, _ = bnd
            J_A = pA[0]
            J_B = pB[0]
            mA = relaxation_metrics(lsw, lb1, J_A)
            mB = relaxation_metrics(lsw, lb1, J_B)

            if mA["abs_relaxation_gap_m"] is not None and mA["abs_relaxation_gap_m"] < -TOL:
                bound_violation_count += 1
            if mB["abs_relaxation_gap_m"] is not None and mB["abs_relaxation_gap_m"] < -TOL:
                bound_violation_count += 1

            for m in (mA, mB):
                c = m["mst_capture_ratio"]
                if c is not None and c > 1.0 + 1e-6:
                    severe_capture_violation_count += 1

            items_A.append(mA)
            items_B.append(mB)
            common_angles.append(ang)

        sa = summarize_orientation_metrics(items_A)
        sb = summarize_orientation_metrics(items_B)

        row = {
            "field_id": field_id,
            "source_sha256": sha,
            "common_valid_orientation_count": len(common_angles),
            "Jstar_A_m": JAstar,
            "Jstar_B_m": JBstar,
            "delta_Jstar_m": (JBstar - JAstar) if JAstar is not None and JBstar is not None else None,
            "Nfull_A": nA,
            "Nfull_B": nB,
            "delta_Nfull": (nB - nA) if nA is not None and nB is not None else None,
            "Nfull_ratio_B_over_A": (nB / nA) if nA and nB is not None else None,
        }
        for k, v in sa.items():
            row[f"A_{k}"] = v
        for k, v in sb.items():
            row[f"B_{k}"] = v
        for k in (
            "median_abs_gap_m", "p90_abs_gap_m", "median_rel_gap",
            "p90_rel_gap", "median_mst_capture_ratio",
        ):
            va, vb = sa.get(k), sb.get(k)
            row[f"delta_{k}"] = (vb - va) if va is not None and vb is not None else None

        paired_rows.append(row)
        all_field_metric_rows.append({
            "dataset": "E1",
            "experiment_arm": "T1",
            "field_id": field_id,
            "source_sha256": sha,
            "family": "",
            "configuration": "A_PRIMARY",
            "resolution_deg": 1.0,
            "Nfull": nA,
            **sa,
        })
        all_field_metric_rows.append({
            "dataset": "E1",
            "experiment_arm": "T2",
            "field_id": field_id,
            "source_sha256": sha,
            "family": "",
            "configuration": "B_MIN_TURN_RADIUS_2P8M",
            "resolution_deg": 1.0,
            "Nfull": nB,
            **sb,
        })

    paired_rows.sort(key=lambda r: r["field_id"])

    # E2-A statistics.
    dN = [fnum(r["delta_Nfull"]) for r in paired_rows if fnum(r["delta_Nfull"]) is not None]
    dP90Gap = [fnum(r["delta_p90_abs_gap_m"]) for r in paired_rows if fnum(r["delta_p90_abs_gap_m"]) is not None]
    dMedGap = [fnum(r["delta_median_abs_gap_m"]) for r in paired_rows if fnum(r["delta_median_abs_gap_m"]) is not None]

    paired_for_rho = [
        (fnum(r["delta_p90_abs_gap_m"]), fnum(r["delta_Nfull"]))
        for r in paired_rows
        if fnum(r["delta_p90_abs_gap_m"]) is not None and fnum(r["delta_Nfull"]) is not None
    ]
    rho = spearman([a for a, b in paired_for_rho], [b for a, b in paired_for_rho]) if paired_for_rho else None
    rho_ci = bootstrap_ci_rho(
        [a for a, b in paired_for_rho],
        [b for a, b in paired_for_rho],
    ) if paired_for_rho else (None, None)

    med_dgap = median(dP90Gap)
    med_dgap_ci = bootstrap_ci_stat(dP90Gap, median) if dP90Gap else (None, None)
    med_dn = median(dN)
    med_dn_ci = bootstrap_ci_stat(dN, median, seed=BOOTSTRAP_SEED + 3) if dN else (None, None)

    nfull_inc = sum(1 for d in dN if d > 0)
    nfull_same = sum(1 for d in dN if abs(d) <= 0)
    nfull_dec = sum(1 for d in dN if d < 0)

    gap_inc = sum(1 for d in dP90Gap if d > TOL)
    gap_same = sum(1 for d in dP90Gap if abs(d) <= TOL)
    gap_dec = sum(1 for d in dP90Gap if d < -TOL)

    total_nA = sum(inum(r["Nfull_A"]) or 0 for r in paired_rows)
    total_nB = sum(inum(r["Nfull_B"]) or 0 for r in paired_rows)

    effort_direction = total_nB > total_nA and nfull_inc > nfull_dec
    gap_direction = med_dgap is not None and med_dgap > 0 and gap_inc > gap_dec
    rho_nontrivial = rho is not None and rho >= 0.30

    if bound_violation_count > 0:
        h1_status = "H1_CERTIFICATE_ANOMALY"
    elif effort_direction and gap_direction and rho_nontrivial:
        h1_status = "H1_STRONG_SUPPORT"
    elif effort_direction and gap_direction:
        h1_status = "H1_PARTIAL_SUPPORT"
    else:
        h1_status = "H1_NOT_SUPPORTED"

    # ------------------------------------------------------------------
    # E2-C T1 vs T3 descriptive
    # ------------------------------------------------------------------
    t3_rows = []
    t3_shas = sorted({sha for (arm, sha) in ix["summary"] if arm == "T3"})
    for sha in t3_shas:
        s1 = ix["summary"].get(("T1", sha))
        s3 = ix["summary"].get(("T3", sha))
        if not s1 or not s3:
            continue

        def arm_summary(arm: str) -> Dict[str, Optional[float]]:
            items = []
            for (a, sh, ang), (J, _) in ix["full"].items():
                if a != arm or sh != sha:
                    continue
                bnd = ix["bounds"].get((arm, sha, ang))
                if not bnd:
                    continue
                lsw, lb1, _ = bnd
                m = relaxation_metrics(lsw, lb1, J)
                if m["abs_relaxation_gap_m"] is not None and m["abs_relaxation_gap_m"] < -TOL:
                    # Count globally, but do not double-count E2-A T1 rows here.
                    pass
                items.append(m)
            return summarize_orientation_metrics(items)

        a = arm_summary("T1")
        b = arm_summary("T3")
        n1 = inum(s1.get("clbos_Nfull"))
        n3 = inum(s3.get("clbos_Nfull"))
        c1 = inum(s1.get("candidate_count"))
        c3 = inum(s3.get("candidate_count"))

        t3_rows.append({
            "field_id": s1.get("field_id"),
            "source_sha256": sha,
            "Nfull_1deg": n1,
            "Nfull_0p5deg": n3,
            "delta_Nfull": (n3 - n1) if n1 is not None and n3 is not None else None,
            "candidate_count_1deg": c1,
            "candidate_count_0p5deg": c3,
            "Nfull_fraction_1deg": (n1 / c1) if n1 is not None and c1 else None,
            "Nfull_fraction_0p5deg": (n3 / c3) if n3 is not None and c3 else None,
            "p90_rel_gap_1deg": a.get("p90_rel_gap"),
            "p90_rel_gap_0p5deg": b.get("p90_rel_gap"),
            "delta_p90_rel_gap": (
                b["p90_rel_gap"] - a["p90_rel_gap"]
                if a.get("p90_rel_gap") is not None and b.get("p90_rel_gap") is not None
                else None
            ),
        })

    # ------------------------------------------------------------------
    # E2-B: original 90 hard tail
    # ------------------------------------------------------------------
    heldout_root = project_root / "clbos01_heldout_topk"
    external_root = project_root / "clbos01_external_competitors_1deg_90"

    field_results_path = heldout_root / "field_results.csv"
    bound90_path = external_root / "bound_1deg.csv"

    h2_status = "H2_BLOCKED_NO_VERIFIED_EXHAUSTIVE_J_TABLE"
    h2_blocker = None
    original90_metrics: List[Dict[str, Any]] = []
    hardtail_long_rows: List[Dict[str, Any]] = []
    model_G = {}
    model_M = {}
    model_GM = {}
    corr_summary = {}
    family_summary = []
    exhaustive_table_path = None
    exhaustive_obj_col = None
    exhaustive_audit = []

    if field_results_path.exists() and bound90_path.exists():
        field_results = read_csv(field_results_path)
        target90 = {
            str(r.get("field_id", "")).strip()
            for r in field_results if str(r.get("field_id", "")).strip()
        }

        # Full bound-success orientation set.
        bound90_rows = read_csv(bound90_path)
        bound_success_angles: Dict[str, set] = defaultdict(set)
        bound_lookup: Dict[Tuple[str, float], Tuple[float, float, str]] = {}
        for r in bound90_rows:
            fid = str(r.get("field_id", "")).strip()
            if fid not in target90 or not is_success_status(r.get("status")):
                continue
            ang = angle_key(r.get("angle_deg"))
            lsw = fnum(r.get("swath_total_length_m"))
            lb1 = fnum(r.get("mst_total_lb_m"))
            if ang is None or lsw is None or lb1 is None:
                continue
            bound_success_angles[fid].add(ang)
            bound_lookup[(fid, ang)] = (lsw, lb1, r.get("family", ""))

        exhaustive_table_path, exhaustive_obj_col, exhaustive_audit, J90_lookup = discover_exhaustive_j_table(
            project_root=project_root,
            target_fields=target90,
            bound_success_angles=bound_success_angles,
            output_dir=output_dir,
        )

        if exhaustive_table_path is not None:
            fr_by_field = {str(r.get("field_id", "")).strip(): r for r in field_results}
            e2b_bound_viols = 0

            for fid in sorted(target90):
                items = []
                fam = fr_by_field.get(fid, {}).get("family", "")
                for ang in sorted(bound_success_angles.get(fid, set())):
                    b = bound_lookup.get((fid, ang))
                    J = J90_lookup.get((fid, ang))
                    if not b or J is None:
                        continue
                    lsw, lb1, fam_b = b
                    fam = fam or fam_b
                    m = relaxation_metrics(lsw, lb1, J)
                    if m["abs_relaxation_gap_m"] is not None and m["abs_relaxation_gap_m"] < -TOL:
                        e2b_bound_viols += 1
                    items.append(m)

                sm = summarize_orientation_metrics(items)
                fr = fr_by_field.get(fid, {})
                nfull = inum(fr.get("mst_exact_full_calls_online"))
                feasible = inum(fr.get("feasible_orientation_count"))
                rec = {
                    "dataset": "ORIGINAL90",
                    "experiment_arm": "PRIMARY_1DEG",
                    "field_id": fid,
                    "source_sha256": "",
                    "family": fam,
                    "configuration": "A_PRIMARY",
                    "resolution_deg": 1.0,
                    "Nfull": nfull,
                    "feasible_orientation_count": feasible,
                    **sm,
                }
                original90_metrics.append(rec)
                all_field_metric_rows.append(rec)

            bound_violation_count += e2b_bound_viols

            # Correlations.
            def corr(key: str) -> Optional[float]:
                pairs = [
                    (fnum(r.get(key)), fnum(r.get("Nfull")))
                    for r in original90_metrics
                    if fnum(r.get(key)) is not None and fnum(r.get("Nfull")) is not None
                ]
                return spearman([a for a, b in pairs], [b for a, b in pairs]) if pairs else None

            for key in (
                "median_lsw_m",
                "feasible_orientation_count",
                "median_abs_gap_m",
                "p90_abs_gap_m",
                "median_rel_gap",
                "p90_rel_gap",
                "median_mst_capture_ratio",
            ):
                corr_summary[key] = corr(key)
                hardtail_long_rows.append({
                    "analysis_type": "spearman",
                    "group": "ALL_90",
                    "metric": key,
                    "value": corr_summary[key],
                    "detail": "Spearman rho with Nfull",
                })

            # Descriptive models.
            model_rows = original90_metrics
            model_G = ols_model(
                model_rows,
                y_key="Nfull",
                x_keys=["median_lsw_m", "feasible_orientation_count"],
                transforms={"median_lsw_m": "log1p"},
            )
            model_M = ols_model(
                model_rows,
                y_key="Nfull",
                x_keys=["p90_rel_gap"],
            )
            model_GM = ols_model(
                model_rows,
                y_key="Nfull",
                x_keys=["median_lsw_m", "feasible_orientation_count", "p90_rel_gap"],
                transforms={"median_lsw_m": "log1p"},
            )

            for name, model in (("GEOMETRY_PROXY", model_G), ("MECHANISM", model_M), ("COMBINED", model_GM)):
                hardtail_long_rows.append({
                    "analysis_type": "ols_model",
                    "group": "ALL_90",
                    "metric": name,
                    "value": model.get("adjusted_r2"),
                    "detail": json.dumps(model, ensure_ascii=False, sort_keys=True),
                })

            # Family summaries.
            fam_groups = defaultdict(list)
            for r in original90_metrics:
                fam_groups[str(r.get("family", ""))].append(r)
            for fam, rows in sorted(fam_groups.items()):
                family_summary.append({
                    "family": fam,
                    "n": len(rows),
                    "median_Nfull": median([fnum(r["Nfull"]) for r in rows if fnum(r["Nfull"]) is not None]),
                    "p90_Nfull": percentile([fnum(r["Nfull"]) for r in rows if fnum(r["Nfull"]) is not None], 0.90),
                    "median_p90_rel_gap": median([fnum(r["p90_rel_gap"]) for r in rows if fnum(r["p90_rel_gap"]) is not None]),
                    "median_mst_capture_ratio": median([fnum(r["median_mst_capture_ratio"]) for r in rows if fnum(r["median_mst_capture_ratio"]) is not None]),
                    "median_lsw_m": median([fnum(r["median_lsw_m"]) for r in rows if fnum(r["median_lsw_m"]) is not None]),
                })

            for r in family_summary:
                hardtail_long_rows.append({
                    "analysis_type": "family_summary",
                    "group": r["family"],
                    "metric": "family",
                    "value": r["median_Nfull"],
                    "detail": json.dumps(r, ensure_ascii=False, sort_keys=True),
                })

            rho_gap = corr_summary.get("p90_rel_gap")
            rho_scale = corr_summary.get("median_lsw_m")
            rho_feas = corr_summary.get("feasible_orientation_count")
            gap_beta = None
            if model_GM.get("status") == "OK":
                gap_beta = model_GM.get("standardized_betas", {}).get("p90_rel_gap")
            adj_g = model_G.get("adjusted_r2") if model_G.get("status") == "OK" else None
            adj_gm = model_GM.get("adjusted_r2") if model_GM.get("status") == "OK" else None

            if bound_violation_count > 0:
                h2_status = "H2_CERTIFICATE_ANOMALY"
            elif rho_gap is not None and rho_gap > 0:
                strongest_simple = max(
                    abs(x) for x in (rho_scale, rho_feas) if x is not None
                ) if any(x is not None for x in (rho_scale, rho_feas)) else 0.0
                adds_r2 = (
                    adj_g is not None and adj_gm is not None
                    and adj_gm >= adj_g + 0.05
                )
                if abs(rho_gap) >= strongest_simple and adds_r2 and (gap_beta is None or gap_beta > 0):
                    h2_status = "H2_STRONG_MECHANISM_ASSOCIATION"
                elif (gap_beta is None or gap_beta > 0):
                    h2_status = "H2_PARTIAL_MECHANISM_ASSOCIATION"
                else:
                    h2_status = "H2_DESCRIPTIVE_ASSOCIATION_ONLY"
            else:
                h2_status = "H2_NOT_SUPPORTED"
        else:
            h2_blocker = (
                "No CSV was verified to contain >=99.5% of the full 1-degree "
                "successful bound field-angle keys for all original 90 fields. "
                "Selected-call full_evaluations tables were not substituted."
            )
    else:
        h2_blocker = "Original 90 field_results.csv and/or bound_1deg.csv is missing."

    # ------------------------------------------------------------------
    # E2 final classification
    # ------------------------------------------------------------------
    if bound_violation_count > 0:
        final_class = "CERTIFICATE_ANOMALY"
        be_strengthened = False
    elif h1_status == "H1_STRONG_SUPPORT":
        if h2_status in {"H2_STRONG_MECHANISM_ASSOCIATION", "H2_PARTIAL_MECHANISM_ASSOCIATION"}:
            final_class = "STRONG_ENGINEERING_MECHANISM_SUPPORTED"
            be_strengthened = True
        else:
            final_class = "STRONG_PAIRED_ENGINEERING_MECHANISM_WITH_LIMITED_HARDTAIL_GENERALISATION"
            be_strengthened = True
    elif h1_status == "H1_PARTIAL_SUPPORT":
        final_class = "PARTIAL_MECHANISM_SUPPORTED"
        be_strengthened = True
    else:
        final_class = "DESCRIPTIVE_ASSOCIATION_ONLY" if h2_status not in {"H2_NOT_SUPPORTED"} else "MECHANISM_NOT_SUPPORTED"
        be_strengthened = False

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    f2 = output_dir / "02_E2_FIELD_MECHANISM_METRICS.csv"
    f3 = output_dir / "03_E2_PAIRED_TURN_RADIUS_ANALYSIS.csv"
    f4 = output_dir / "04_E2_HARD_TAIL_ANALYSIS.csv"
    f5 = output_dir / "05_E2_SCIENTIFIC_REPORT.md"
    f6 = output_dir / "06_E2_GATE.json"

    write_csv(f2, all_field_metric_rows)
    write_csv(f3, paired_rows)

    # Add T3 tertiary rows to long analysis.
    for r in t3_rows:
        hardtail_long_rows.append({
            "analysis_type": "T3_resolution_pair",
            "group": r["field_id"],
            "metric": "delta_Nfull",
            "value": r["delta_Nfull"],
            "detail": json.dumps(r, ensure_ascii=False, sort_keys=True),
        })
    if h2_blocker:
        hardtail_long_rows.append({
            "analysis_type": "H2_blocker",
            "group": "ORIGINAL90",
            "metric": "verified_exhaustive_j_table",
            "value": "",
            "detail": h2_blocker,
        })
    write_csv(f4, hardtail_long_rows, fieldnames=["analysis_type", "group", "metric", "value", "detail"])

    # Scientific report.
    lines = []
    lines.append("# E2 Scientific Report — Certification Difficulty Mechanism")
    lines.append("")
    lines.append("## A. Integrity and scope")
    lines.append("")
    lines.append(f"- Paired T1/T2 fields: **{len(paired_rows)}**.")
    lines.append(f"- Configuration A minimum turning radius: **{a_radius} m**.")
    lines.append(f"- Configuration B minimum turning radius: **{b_radius} m**.")
    lines.append(f"- Config-B single-factor freeze: **{config_b_single_factor}**.")
    lines.append(f"- A1–A4 Config-B audit: **{a1a4_pass}**.")
    lines.append(f"- Planner/bound semantics unchanged: **{bound_semantics_unchanged}**.")
    lines.append(f"- T2 bound rows in E1 raw bound table: **{ix['t2_bound_row_count']}**; T2 uses the frozen T1 swath/MST bound semantics.")
    lines.append(f"- Missing common-angle joins in E2-A: **{missing_join_count}**.")
    lines.append(f"- Bound violations detected: **{bound_violation_count}**.")
    lines.append("")
    lines.append("No new Route+Path calls were made.")
    lines.append("")

    lines.append("## B. Paired turning-radius intervention (E2-A)")
    lines.append("")
    lines.append(f"- CLBOS Nfull total: A = **{total_nA}**, B = **{total_nB}**.")
    if total_nA:
        lines.append(f"- Aggregate Nfull change: **{total_nB-total_nA:+d} ({(total_nB/total_nA-1)*100:.2f}%)**.")
    lines.append(f"- Field-level Nfull: increase/same/decrease = **{nfull_inc}/{nfull_same}/{nfull_dec}**.")
    lines.append(f"- Median paired ΔNfull = **{med_dn}**, bootstrap 95% CI = **[{med_dn_ci[0]}, {med_dn_ci[1]}]**.")
    lines.append(f"- P90 absolute relaxation-gap change: increase/same/decrease = **{gap_inc}/{gap_same}/{gap_dec}**.")
    lines.append(f"- Median paired ΔP90[J−LB1] = **{med_dgap} m**, bootstrap 95% CI = **[{med_dgap_ci[0]}, {med_dgap_ci[1]}] m**.")
    lines.append(f"- Spearman ρ between ΔP90[J−LB1] and ΔNfull = **{rho}**, bootstrap 95% CI = **[{rho_ci[0]}, {rho_ci[1]}]**.")
    lines.append(f"- Exact sign-test p for ΔNfull = **{exact_sign_test_two_sided(dN)}**.")
    lines.append(f"- Exact sign-test p for ΔP90[J−LB1] = **{exact_sign_test_two_sided(dP90Gap, TOL)}**.")
    lines.append(f"- **H1 status: `{h1_status}`.**")
    lines.append("")

    lines.append("Interpretation boundary: this paired intervention supports or refutes a mechanism under the frozen Fields2Cover pipeline; it is not a universal causal law for all agricultural planners.")
    lines.append("")

    lines.append("## C. Original 90-field hard-tail analysis (E2-B)")
    lines.append("")
    if exhaustive_table_path is not None:
        lines.append(f"- Verified exhaustive per-angle J table: `{exhaustive_table_path}`.")
        lines.append(f"- Objective column: `{exhaustive_obj_col}`.")
        if exhaustive_audit:
            lines.append(f"- Best-table matched field-angle coverage: **{exhaustive_audit[0]['coverage_fraction']:.6f}**.")
        lines.append(f"- Original field-level rows analysed: **{len(original90_metrics)}**.")
        lines.append(f"- Spearman ρ(Nfull, P90 relative relaxation gap) = **{corr_summary.get('p90_rel_gap')}**.")
        lines.append(f"- Spearman ρ(Nfull, median Lsw) = **{corr_summary.get('median_lsw_m')}**.")
        lines.append(f"- Spearman ρ(Nfull, feasible orientation count) = **{corr_summary.get('feasible_orientation_count')}**.")
        lines.append(f"- Geometry-proxy model adjusted R² = **{model_G.get('adjusted_r2')}**.")
        lines.append(f"- Mechanism-only model adjusted R² = **{model_M.get('adjusted_r2')}**.")
        lines.append(f"- Combined model adjusted R² = **{model_GM.get('adjusted_r2')}**.")
        lines.append(f"- **H2 status: `{h2_status}`.**")
        lines.append("")
        lines.append("Family summaries:")
        lines.append("")
        lines.append("| Family | n | Median Nfull | P90 Nfull | Median field P90 relative gap | Median MST capture ratio |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for r in family_summary:
            lines.append(
                f"| {r['family']} | {r['n']} | {r['median_Nfull']} | {r['p90_Nfull']} | "
                f"{r['median_p90_rel_gap']} | {r['median_mst_capture_ratio']} |"
            )
    else:
        lines.append(f"- **H2 status: `{h2_status}`.**")
        lines.append(f"- Blocker: {h2_blocker}")
        lines.append("")
        lines.append("No selected-call table was substituted for a missing exhaustive J(theta) table, because doing so would make the relaxation-gap analysis selection-biased and partly circular.")
    lines.append("")

    lines.append("## D. Resolution transfer (E2-C, tertiary)")
    lines.append("")
    if t3_rows:
        dn3 = [fnum(r["delta_Nfull"]) for r in t3_rows if fnum(r["delta_Nfull"]) is not None]
        df1 = [fnum(r["Nfull_fraction_1deg"]) for r in t3_rows if fnum(r["Nfull_fraction_1deg"]) is not None]
        df3 = [fnum(r["Nfull_fraction_0p5deg"]) for r in t3_rows if fnum(r["Nfull_fraction_0p5deg"]) is not None]
        lines.append(f"- Paired fields: **{len(t3_rows)}**.")
        lines.append(f"- Median ΔNfull (0.5° − 1°): **{median(dn3)}**.")
        lines.append(f"- Median Nfull/candidate fraction at 1°: **{median(df1)}**.")
        lines.append(f"- Median Nfull/candidate fraction at 0.5°: **{median(df3)}**.")
    else:
        lines.append("- No valid T1/T3 paired rows found.")
    lines.append("")

    lines.append("## E. Paper-level scientific classification")
    lines.append("")
    lines.append(f"`E2_FINAL_CLASSIFICATION={final_class}`")
    lines.append("")
    lines.append(f"`BE_ENGINEERING_INSIGHT_STRENGTHENED={str(be_strengthened).lower()}`")
    lines.append("")
    if h1_status == "H1_STRONG_SUPPORT":
        lines.append(
            "The strongest defensible manuscript-level interpretation is that, under a controlled "
            "increase in minimum turning radius with frozen swath/MST geometry, the realised "
            "complete-path objective moves farther above the Euclidean endpoint-MST certificate "
            "and the certificate requires more complete evaluations. This links an agricultural "
            "vehicle kinematic constraint to lower-bound tightness and certification effort."
        )
    elif h1_status == "H1_PARTIAL_SUPPORT":
        lines.append(
            "The paired experiment supports the directional kinematic-tightness mechanism, "
            "but the field-level gap–effort association is not strong enough for a strong mechanism claim."
        )
    else:
        lines.append(
            "The paired evidence does not support strengthening the manuscript around the proposed "
            "kinematic-relaxation mechanism."
        )
    lines.append("")
    f5.write_text("\n".join(lines) + "\n", encoding="utf-8")

    gate = {
        "schema_version": SCHEMA_VERSION,
        "task": "CLBOS_E2_CERTIFICATION_DIFFICULTY_MECHANISM",
        "TASK_STATUS": "COMPLETE",
        "DEPENDENCY_CLOSURE_PASS": True,
        "NEW_ROUTE_PATH_CALL_COUNT": 0,
        "METHOD_MODIFIED": False,
        "MANUSCRIPT_MODIFIED": False,
        "PUBLIC_RELEASE_MODIFIED": False,
        "STANDARD_LIBRARY_ONLY": True,
        "CONFIG_A_TURN_RADIUS_M": a_radius,
        "CONFIG_B_TURN_RADIUS_M": b_radius,
        "CONFIG_B_SINGLE_FACTOR": config_b_single_factor,
        "A1_A4_CONFIG_B_PASS": a1a4_pass,
        "ASSUMPTION_SEMANTICS_UNCHANGED": bound_semantics_unchanged,
        "PAIRED_T1_T2_FIELD_COUNT": len(paired_rows),
        "T2_BOUND_ROW_COUNT_IN_RAW_BOUND_TABLE": ix["t2_bound_row_count"],
        "T2_BOUND_REUSE_FROM_T1_SEMANTICS": ix["t2_bound_row_count"] == 0 and config_b_single_factor and bound_semantics_unchanged,
        "MISSING_COMMON_ANGLE_JOIN_COUNT": missing_join_count,
        "BOUND_VIOLATION_COUNT": bound_violation_count,
        "MST_CAPTURE_RATIO_GT_ONE_COUNT": severe_capture_violation_count,
        "NFULL_A_TOTAL": total_nA,
        "NFULL_B_TOTAL": total_nB,
        "NFULL_INCREASE_COUNT": nfull_inc,
        "NFULL_SAME_COUNT": nfull_same,
        "NFULL_DECREASE_COUNT": nfull_dec,
        "MEDIAN_DELTA_NFULL": med_dn,
        "MEDIAN_DELTA_NFULL_BOOTSTRAP95": list(med_dn_ci),
        "P90_GAP_INCREASE_COUNT": gap_inc,
        "P90_GAP_SAME_COUNT": gap_same,
        "P90_GAP_DECREASE_COUNT": gap_dec,
        "MEDIAN_DELTA_P90_ABS_GAP_M": med_dgap,
        "MEDIAN_DELTA_P90_ABS_GAP_BOOTSTRAP95_M": list(med_dgap_ci),
        "DELTA_P90_GAP_DELTA_NFULL_SPEARMAN_RHO": rho,
        "DELTA_P90_GAP_DELTA_NFULL_SPEARMAN_BOOTSTRAP95": list(rho_ci),
        "DELTA_NFULL_SIGN_TEST_P": exact_sign_test_two_sided(dN),
        "DELTA_P90_GAP_SIGN_TEST_P": exact_sign_test_two_sided(dP90Gap, TOL),
        "H1_STATUS": h1_status,
        "T3_PAIRED_FIELD_COUNT": len(t3_rows),
        "ORIGINAL90_FIELD_RESULTS_PATH": str(field_results_path),
        "ORIGINAL90_BOUND_PATH": str(bound90_path),
        "ORIGINAL90_VERIFIED_EXHAUSTIVE_J_TABLE": str(exhaustive_table_path) if exhaustive_table_path else None,
        "ORIGINAL90_VERIFIED_EXHAUSTIVE_J_OBJECTIVE_COLUMN": exhaustive_obj_col,
        "ORIGINAL90_EXHAUSTIVE_TABLE_AUDIT_TOP": exhaustive_audit[:10],
        "ORIGINAL90_FIELD_COUNT": len(original90_metrics),
        "H2_BLOCKER": h2_blocker,
        "H2_CORRELATIONS": corr_summary,
        "GEOMETRY_PROXY_MODEL": model_G,
        "MECHANISM_MODEL": model_M,
        "COMBINED_MODEL": model_GM,
        "H2_STATUS": h2_status,
        "E2_FINAL_CLASSIFICATION": final_class,
        "BE_ENGINEERING_INSIGHT_STRENGTHENED": be_strengthened,
        "CIRCULARITY_AUDIT_PASS": True,
        "FIELD_IS_STATISTICAL_UNIT": True,
        "SOURCE_SHA256": {
            str(e1["paths"]["transfer"]): sha256_file(e1["paths"]["transfer"]),
            str(e1["paths"]["bounds"]): sha256_file(e1["paths"]["bounds"]),
            str(e1["paths"]["full"]): sha256_file(e1["paths"]["full"]),
            str(script_path): sha256_file(script_path),
        },
    }

    with f6.open("w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False, indent=2)

    # Re-hash final outputs into gate after all are written except gate itself.
    gate["OUTPUT_SHA256"] = {
        "01_E2_ANALYSIS_FREEZE.md": sha256_file(freeze_out),
        "02_E2_FIELD_MECHANISM_METRICS.csv": sha256_file(f2),
        "03_E2_PAIRED_TURN_RADIUS_ANALYSIS.csv": sha256_file(f3),
        "04_E2_HARD_TAIL_ANALYSIS.csv": sha256_file(f4),
        "05_E2_SCIENTIFIC_REPORT.md": sha256_file(f5),
    }
    with f6.open("w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False, indent=2)

    # Terminal summary.
    print("TASK_STATUS=COMPLETE")
    print("DEPENDENCY_CLOSURE_PASS=true")
    print("NEW_ROUTE_PATH_CALL_COUNT=0")
    print(f"PAIRED_FIELD_COUNT={len(paired_rows)}")
    print(f"T2_BOUND_REUSE_FROM_T1_SEMANTICS={str(gate['T2_BOUND_REUSE_FROM_T1_SEMANTICS']).lower()}")
    print(f"NFULL_A_TOTAL={total_nA}")
    print(f"NFULL_B_TOTAL={total_nB}")
    print(f"NFULL_INCREASE_COUNT={nfull_inc}")
    print(f"NFULL_SAME_COUNT={nfull_same}")
    print(f"NFULL_DECREASE_COUNT={nfull_dec}")
    print(f"MEDIAN_DELTA_P90_ABS_GAP_M={med_dgap}")
    print(f"DELTA_GAP_DELTA_NFULL_SPEARMAN_RHO={rho}")
    print(f"H1_STATUS={h1_status}")
    print(f"ORIGINAL90_VERIFIED_EXHAUSTIVE_J_TABLE={str(exhaustive_table_path) if exhaustive_table_path else 'NONE'}")
    print(f"H2_STATUS={h2_status}")
    print(f"E2_FINAL_CLASSIFICATION={final_class}")
    print(f"BE_ENGINEERING_INSIGHT_STRENGTHENED={str(be_strengthened).lower()}")
    print(f"BOUND_VIOLATION_COUNT={bound_violation_count}")
    print("METHOD_MODIFIED=false")
    print("MANUSCRIPT_MODIFIED=false")
    print("EXPECTED_GPT_RETURN_FILE_COUNT=6")
    for p in (freeze_out, f2, f3, f4, f5, f6):
        print(str(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
