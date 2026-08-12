#!/usr/bin/env python3
import csv, json, math, os, statistics, subprocess, time
from pathlib import Path

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
CACHE = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve()
FULL_BIN = CACHE / "Fields2Cover-build/agri_f2c_runner"

BASE = ROOT / "clbos01_external_competitors_1deg_90"
SELECTED = ROOT / "clbos01_heldout_topk/selected_heldout_fields.csv"
BOUND = BASE / "bound_1deg.csv"
FULL = BASE / "full_evaluations.csv"
ORACLE = BASE / "field_results.csv"

OUT = BASE / "oksanen_matched_1deg_results.csv"
SUMMARY = BASE / "oksanen_matched_1deg_summary.csv"
TRACE = BASE / "oksanen_matched_1deg_trace.csv"

TIMEOUT = 900

def read_csv(p):
    with p.open(newline="", encoding="utf-8") as f:
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
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)

def nearest_int_angle(x):
    y = x % 180.0
    return int(math.floor(y + 0.5)) % 180

def full_map():
    d = {}
    if FULL.exists():
        for r in read_csv(FULL):
            if r["status"] == "SUCCESS":
                d[(r["field_id"], int(r["angle_deg"]))] = r
    return d

def ensure_full(field, angle, done):
    key = (field["field_id"], angle)
    if key in done:
        return done[key]
    fields = ["field_id","family","angle_deg","status","complete_path_length_m","wall_seconds","error"]
    t0 = time.monotonic()
    p = subprocess.run(
        [str(FULL_BIN), "--wkt-file", field["local_wkt_path"], "--angle-deg", str(angle)],
        text=True, capture_output=True, timeout=TIMEOUT
    )
    wall = time.monotonic() - t0
    if p.returncode == 0:
        d = json.loads(p.stdout)
        row = {
            "field_id": field["field_id"], "family": field["family"], "angle_deg": angle,
            "status": "SUCCESS", "complete_path_length_m": d["complete_path_length_m"],
            "wall_seconds": f"{wall:.9f}", "error": ""
        }
        done[key] = row
    else:
        row = {
            "field_id": field["field_id"], "family": field["family"], "angle_deg": angle,
            "status": "FAILED", "wall_seconds": f"{wall:.9f}", "error": p.stderr.strip()
        }
    append(FULL, fields, row)
    return row

def oksanen_schedule(cost):
    evaluated = set([0,30,60,90,120,150])
    trace = []
    step = 30.0
    round_idx = 0

    def ranked():
        feasible = [a for a in evaluated if a in cost]
        return sorted(feasible, key=lambda a: (cost[a], a))

    best3 = ranked()[:3]
    trace.append((round_idx, step, len(evaluated), tuple(best3)))

    while True:
        step /= 2.0
        round_idx += 1
        new = set()
        for center in best3:
            new.add(nearest_int_angle(center-step))
            new.add(nearest_int_angle(center+step))
        evaluated.update(new)
        best3 = ranked()[:3]
        trace.append((round_idx, step, len(evaluated), tuple(best3)))
        if step < 1.0:
            break

    winner = ranked()[0]
    return winner, evaluated, trace

def main():
    for p in [FULL_BIN, SELECTED, BOUND, ORACLE]:
        if not p.exists():
            raise RuntimeError(f"Missing: {p}")

    fields = {r["field_id"]: r for r in read_csv(SELECTED)}
    oracle = {r["field_id"]: r for r in read_csv(ORACLE) if r["status"] == "COMPLETE"}

    costs = {}
    for r in read_csv(BOUND):
        if r["status"] == "SUCCESS":
            costs.setdefault(r["field_id"], {})[int(r["angle_deg"])] = float(r["swath_total_length_m"])

    done = full_map()
    results = []
    traces = []

    for idx, fid in enumerate(sorted(fields), 1):
        if fid not in oracle:
            raise RuntimeError(f"Missing oracle: {fid}")
        if len(costs.get(fid, {})) == 0:
            raise RuntimeError(f"No LSW costs: {fid}")

        winner, evaluated, tr = oksanen_schedule(costs[fid])
        fr = ensure_full(fields[fid], winner, done)
        if fr["status"] != "SUCCESS":
            raise RuntimeError(f"Full failure {fid} angle={winner}: {fr['error']}")

        j = float(fr["complete_path_length_m"])
        jstar = float(oracle[fid]["oracle_j_star_m"])
        regret = j / jstar - 1.0

        for round_idx, step, n_eval, best3 in tr:
            traces.append({
                "field_id": fid, "family": fields[fid]["family"],
                "round": round_idx, "nominal_step_deg": step,
                "unique_1deg_candidates_evaluated": n_eval,
                "best3_angles": ";".join(map(str, best3)),
            })

        results.append({
            "field_id": fid, "family": fields[fid]["family"],
            "winner_angle_deg": winner,
            "j_m": f"{j:.12f}", "oracle_j_star_m": f"{jstar:.12f}",
            "regret": f"{regret:.12f}", "exact": regret <= 1e-9,
            "cheap_angle_evals": len(evaluated), "full_calls": 1,
            "definition": "Oksanen matched discrete adaptation: 6 initial directions, retain best 3, halve step, add +/-step candidates, stop below 1deg; candidates snapped to common 1deg domain",
        })
        print(f"[{idx}/90] {fid}: angle={winner} exact={regret<=1e-9} regret={100*regret:.4f}% cheap={len(evaluated)}", flush=True)

    atomic(OUT, results)
    atomic(TRACE, traces)

    regs = [float(r["regret"]) for r in results]
    exact = sum(str(r["exact"]).lower() == "true" for r in results)
    summary = [{
        "method": "OKSANEN_MATCHED_1DEG",
        "field_count": len(results),
        "exact_count": exact,
        "exact_rate": exact / len(results),
        "median_regret": statistics.median(regs),
        "p90_regret": statistics.quantiles(regs, n=10, method="inclusive")[8],
        "p95_regret": statistics.quantiles(regs, n=20, method="inclusive")[18],
        "max_regret": max(regs),
        "nonzero_regret_count": sum(x > 1e-12 for x in regs),
        "median_cheap_angle_evals": statistics.median(int(r["cheap_angle_evals"]) for r in results),
        "min_cheap_angle_evals": min(int(r["cheap_angle_evals"]) for r in results),
        "max_cheap_angle_evals": max(int(r["cheap_angle_evals"]) for r in results),
        "median_full_calls": 1,
    }]
    atomic(SUMMARY, summary)

    s = summary[0]
    print("\n=== OKSANEN MATCHED 1DEG SUMMARY ===")
    print(
        f"exact={s['exact_count']}/{s['field_count']} ({100*s['exact_rate']:.1f}%) "
        f"nonzero_regret={s['nonzero_regret_count']} "
        f"p90={100*s['p90_regret']:.4f}% p95={100*s['p95_regret']:.4f}% "
        f"max={100*s['max_regret']:.4f}% "
        f"median_cheap={s['median_cheap_angle_evals']} "
        f"range_cheap=[{s['min_cheap_angle_evals']},{s['max_cheap_angle_evals']}]"
    )
    print("Outputs:", OUT, SUMMARY, TRACE)

if __name__ == "__main__":
    main()
