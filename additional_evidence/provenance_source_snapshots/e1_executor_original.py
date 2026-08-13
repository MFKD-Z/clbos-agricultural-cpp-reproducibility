# PUBLIC NOTE: path-sanitized source snapshot of the executed experiment script; not the portable reproduction entry point.
#!/usr/bin/env python3
"""Frozen E1 executor. It never changes K, bounds, subsets, or outcome gates."""

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E1 = Path(__file__).resolve().parent
FREEZE = E1 / "03_E1_SELECTION_AND_CONFIG_FREEZE.json"
RESULTS = E1 / "04_E1_TRANSFER_RESULTS.csv"
RAW = E1 / "raw"
BOUND_RAW = RAW / "candidate_bounds.csv"
FULL_RAW = RAW / "candidate_full_paths.csv"
SMOKE = RAW / "smoke_replay.json"

MST_BIN = Path("/path/to/agri_runtime/Fields2Cover-build/agri_f2c_mst_probe")
FULL_A_BIN = Path("/path/to/agri_runtime/Fields2Cover-build/agri_f2c_runner")

FROZEN_K = 10
EPS = 1e-6
EXACT_TOL = 1e-9
TIMEOUT = 900

BOUND_FIELDS = [
    "experiment_arm", "field_id", "source_sha256", "angle_deg", "status",
    "swath_total_length_m", "mst_total_lb_m", "error",
]
FULL_FIELDS = [
    "experiment_arm", "field_id", "source_sha256", "configuration_id",
    "angle_deg", "status", "complete_path_length_m", "error",
]
RESULT_FIELDS = [
    "experiment_arm", "field_id", "source_sha256", "configuration_id",
    "orientation_resolution_deg", "candidate_count", "oracle_J",
    "oracle_orientation", "oracle_swathlength_rank", "top10_J",
    "top10_orientation", "top10_exact", "top10_absolute_excess_m",
    "top10_relative_regret", "top10_Nfull", "top10_oracle_rank",
    "clbos_J", "clbos_orientation", "clbos_exact", "clbos_Nfull",
    "clbos_certificate_status", "execution_failure_count",
    "model_infeasible_count", "result_status",
]


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def append_csv(path, fields, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def atomic_csv(path, fields, rows):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def angle_key(angle):
    return f"{angle:.10g}"


def load_resolved(path, key_columns, allowed):
    resolved = {}
    failures = []
    for row in read_csv(path):
        key = tuple(row[column] for column in key_columns)
        if row["status"] in allowed:
            resolved[key] = row
        else:
            failures.append(row)
    if failures:
        first = failures[0]
        raise RuntimeError(
            f"Existing unresolved failure in {path}: "
            f"{first.get('field_id')} angle={first.get('angle_deg')} "
            f"status={first.get('status')}; automatic retry is prohibited"
        )
    return resolved


def run_json(binary, args):
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [str(binary), *args], text=True, capture_output=True,
            timeout=TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return "EXECUTION_FAILURE", None, f"TIMEOUT:{exc}", time.monotonic() - started
    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        error = (proc.stderr or proc.stdout).strip()
        if "no swaths generated" in error:
            return "INFEASIBLE_NO_SWATHS", None, "", elapsed
        return "EXECUTION_FAILURE", None, error[:2000], elapsed
    try:
        return "SUCCESS", json.loads(proc.stdout.strip().splitlines()[-1]), "", elapsed
    except Exception as exc:  # preserved as execution failure
        return "EXECUTION_FAILURE", None, f"MALFORMED_JSON:{exc}", elapsed


def ensure_bound(field, arm, angle, cache):
    key = (arm, field["field_id"], angle_key(angle))
    if key in cache:
        return cache[key]
    status, data, error, _ = run_json(
        MST_BIN,
        ["--wkt-file", field["local_wkt_path"], "--angle-deg", angle_key(angle), "--mst-probe"],
    )
    row = {
        "experiment_arm": arm,
        "field_id": field["field_id"],
        "source_sha256": field["source_sha256"],
        "angle_deg": angle_key(angle),
        "status": status,
        "swath_total_length_m": "" if data is None else f"{float(data['swath_total_length_m']):.12f}",
        "mst_total_lb_m": "" if data is None else f"{float(data['mst_total_lb_m']):.12f}",
        "error": error,
    }
    append_csv(BOUND_RAW, BOUND_FIELDS, row)
    if status == "EXECUTION_FAILURE":
        raise RuntimeError(f"Bound execution failure {field['field_id']} angle={angle_key(angle)}: {error}")
    cache[key] = row
    return row


def ensure_full(field, arm, configuration_id, binary, angle, cache):
    key = (arm, field["field_id"], configuration_id, angle_key(angle))
    if key in cache:
        return cache[key]
    status, data, error, _ = run_json(
        binary,
        ["--wkt-file", field["local_wkt_path"], "--angle-deg", angle_key(angle)],
    )
    # A candidate that was feasible in the bound sweep must not be relabeled infeasible here.
    if status == "INFEASIBLE_NO_SWATHS":
        status = "EXECUTION_FAILURE"
        error = "FULL_RUNNER_NO_SWATHS_AFTER_FEASIBLE_BOUND"
    row = {
        "experiment_arm": arm,
        "field_id": field["field_id"],
        "source_sha256": field["source_sha256"],
        "configuration_id": configuration_id,
        "angle_deg": angle_key(angle),
        "status": status,
        "complete_path_length_m": "" if data is None else f"{float(data['complete_path_length_m']):.12f}",
        "error": error,
    }
    append_csv(FULL_RAW, FULL_FIELDS, row)
    if status != "SUCCESS":
        raise RuntimeError(f"Full execution failure {field['field_id']} angle={angle_key(angle)}: {error}")
    cache[key] = row
    return row


def exact(j, oracle):
    return j / oracle - 1.0 <= EXACT_TOL


def summarize_field(field, arm, configuration_id, resolution, angles, bounds, fulls):
    feasible = []
    infeasible = 0
    for angle in angles:
        b = bounds[(arm if arm != "T2" else "T1", field["field_id"], angle_key(angle))]
        if b["status"] == "INFEASIBLE_NO_SWATHS":
            infeasible += 1
            continue
        f = fulls[(arm, field["field_id"], configuration_id, angle_key(angle))]
        feasible.append({
            "angle": float(angle),
            "swath": float(b["swath_total_length_m"]),
            "mst": float(b["mst_total_lb_m"]),
            "j": float(f["complete_path_length_m"]),
        })
    if not feasible:
        raise RuntimeError(f"No feasible candidate for {arm} {field['field_id']}")

    oracle = min(row["j"] for row in feasible)
    oracle_rows = [row for row in feasible if exact(row["j"], oracle)]
    oracle_angles = sorted(row["angle"] for row in oracle_rows)
    swath_order = sorted(feasible, key=lambda row: (row["swath"], row["angle"]))
    oracle_rank = min(i + 1 for i, row in enumerate(swath_order) if exact(row["j"], oracle))

    top = swath_order[:FROZEN_K]
    top_best = min(top, key=lambda row: (row["j"], row["angle"]))
    top_regret = top_best["j"] / oracle - 1.0

    bound_legal = all(row["mst"] <= row["j"] + EPS for row in feasible)
    mst_order = sorted(feasible, key=lambda row: (row["mst"], row["angle"]))
    incumbent = math.inf
    incumbent_angle = None
    nfull = 0
    stopped = False
    for row in mst_order:
        if row["mst"] >= incumbent + EPS:
            stopped = True
            break
        nfull += 1
        if row["j"] < incumbent or (
            math.isclose(row["j"], incumbent, rel_tol=EXACT_TOL, abs_tol=EPS)
            and (incumbent_angle is None or row["angle"] < incumbent_angle)
        ):
            incumbent = row["j"]
            incumbent_angle = row["angle"]
    clbos_exact = exact(incumbent, oracle)
    if not bound_legal:
        certificate = "BOUND_VIOLATION"
    elif not clbos_exact:
        certificate = "NONEXACT_ANOMALY"
    elif stopped or nfull == len(mst_order):
        certificate = "CERTIFIED_EXACT"
    else:
        certificate = "UNRESOLVED"

    return {
        "experiment_arm": arm,
        "field_id": field["field_id"],
        "source_sha256": field["source_sha256"],
        "configuration_id": configuration_id,
        "orientation_resolution_deg": f"{resolution:g}",
        "candidate_count": len(angles),
        "oracle_J": f"{oracle:.12f}",
        "oracle_orientation": ";".join(angle_key(a) for a in oracle_angles),
        "oracle_swathlength_rank": oracle_rank,
        "top10_J": f"{top_best['j']:.12f}",
        "top10_orientation": angle_key(top_best["angle"]),
        "top10_exact": str(top_regret <= EXACT_TOL).lower(),
        "top10_absolute_excess_m": f"{top_best['j'] - oracle:.12f}",
        "top10_relative_regret": f"{top_regret:.12f}",
        "top10_Nfull": len(top),
        "top10_oracle_rank": oracle_rank,
        "clbos_J": f"{incumbent:.12f}",
        "clbos_orientation": angle_key(incumbent_angle),
        "clbos_exact": str(clbos_exact).lower(),
        "clbos_Nfull": nfull,
        "clbos_certificate_status": certificate,
        "execution_failure_count": 0,
        "model_infeasible_count": infeasible,
        "result_status": "COMPLETE" if certificate == "CERTIFIED_EXACT" else "SCIENTIFIC_ANOMALY",
    }


def run_arm(fields, arm, configuration_id, resolution, angles, full_binary, bound_cache, full_cache, results):
    existing = {(r["experiment_arm"], r["field_id"]): r for r in results}
    bound_arm = "T1" if arm == "T2" else arm
    for field_index, field in enumerate(fields, 1):
        if (arm, field["field_id"]) in existing:
            print(f"[{arm} {field_index}/{len(fields)}] {field['field_id']} RESULT_RESUME_SKIP", flush=True)
            continue
        for index, angle in enumerate(angles, 1):
            bound = ensure_bound(field, bound_arm, angle, bound_cache)
            if bound["status"] == "SUCCESS":
                ensure_full(field, arm, configuration_id, full_binary, angle, full_cache)
            if index % 30 == 0 or index == len(angles):
                print(
                    f"[{arm} {field_index}/{len(fields)}] {field['field_id']} "
                    f"candidate={index}/{len(angles)}",
                    flush=True,
                )
        row = summarize_field(field, arm, configuration_id, resolution, angles, bound_cache, full_cache)
        results.append(row)
        atomic_csv(RESULTS, RESULT_FIELDS, results)
        print(
            f"[{arm} {field_index}/{len(fields)}] COMPLETE "
            f"Top10={row['top10_exact']} CLBOS={row['clbos_exact']} "
            f"Nfull={row['clbos_Nfull']}",
            flush=True,
        )
        if row["clbos_exact"] != "true" or row["clbos_certificate_status"] != "CERTIFIED_EXACT":
            raise RuntimeError(f"E1 scientific anomaly at {arm} {field['field_id']}; no rescue run authorized")


def smoke(config_b_binary):
    selected = read_csv(ROOT / "clbos01_heldout_topk" / "selected_heldout_fields.csv")
    stored_bound = read_csv(ROOT / "clbos01_external_competitors_1deg_90" / "bound_1deg.csv")
    stored_full = read_csv(ROOT / "clbos01_external_competitors_1deg_90" / "full_evaluations.csv")
    stored_field = read_csv(ROOT / "clbos01_external_competitors_1deg_90" / "field_results.csv")
    stored_topk = read_csv(ROOT / "clbos01_1deg_topk_closure" / "topk_field_results.csv")
    field = selected[0]
    fid = field["field_id"]
    bound_rows = [r for r in stored_bound if r["field_id"] == fid and r["status"] == "SUCCESS"]
    full_map = {
        int(float(r["angle_deg"])): r for r in stored_full
        if r["field_id"] == fid and r["status"] == "SUCCESS"
    }
    replay_angles = sorted(full_map)[:2]
    if len(replay_angles) != 2:
        raise RuntimeError("Old-data smoke cannot locate two frozen full rows")
    action_checks = []
    for angle in replay_angles:
        b_status, b_data, b_error, _ = run_json(
            MST_BIN, ["--wkt-file", field["local_wkt_path"], "--angle-deg", str(angle), "--mst-probe"]
        )
        a_status, a_data, a_error, _ = run_json(
            FULL_A_BIN, ["--wkt-file", field["local_wkt_path"], "--angle-deg", str(angle)]
        )
        c_status, c_data, c_error, _ = run_json(
            config_b_binary, ["--wkt-file", field["local_wkt_path"], "--angle-deg", str(angle)]
        )
        old_b = next(r for r in bound_rows if int(float(r["angle_deg"])) == angle)
        old_f = full_map[angle]
        action_checks.append({
            "angle": angle,
            "bound_status": b_status,
            "full_A_status": a_status,
            "full_B_status": c_status,
            "bound_replay_exact": b_status == "SUCCESS" and math.isclose(
                float(b_data["mst_total_lb_m"]), float(old_b["mst_total_lb_m"]), rel_tol=1e-12, abs_tol=1e-9
            ),
            "full_A_replay_exact": a_status == "SUCCESS" and math.isclose(
                float(a_data["complete_path_length_m"]), float(old_f["complete_path_length_m"]), rel_tol=1e-12, abs_tol=1e-9
            ),
            "full_B_positive": c_status == "SUCCESS" and float(c_data["complete_path_length_m"]) > 0,
            "errors": [b_error, a_error, c_error],
        })

    swath_order = sorted(bound_rows, key=lambda r: (float(r["swath_total_length_m"]), int(r["angle_deg"])))
    top = swath_order[:FROZEN_K]
    top_j = min(float(full_map[int(r["angle_deg"])]["complete_path_length_m"]) for r in top)
    top_ref = next(r for r in stored_topk if r["field_id"] == fid and r["k"] == "10")
    oracle_ref = next(r for r in stored_field if r["field_id"] == fid)
    incumbent = math.inf
    calls = 0
    for row in sorted(bound_rows, key=lambda r: (float(r["mst_total_lb_m"]), int(r["angle_deg"]))):
        if float(row["mst_total_lb_m"]) >= incumbent + EPS:
            break
        angle = int(row["angle_deg"])
        if angle not in full_map:
            raise RuntimeError(f"Missing old full row needed for CLBOS replay: {fid} {angle}")
        calls += 1
        incumbent = min(incumbent, float(full_map[angle]["complete_path_length_m"]))
    smoke_result = {
        "status": "PASS",
        "science_table_inclusion": False,
        "old_field_id": fid,
        "action_checks": action_checks,
        "top10_deterministic_replay_pass": math.isclose(top_j, float(top_ref["topk_best_j_m"]), rel_tol=1e-12, abs_tol=1e-9),
        "clbos_deterministic_replay_pass": calls == int(oracle_ref["mst_certified_full_calls"]),
        "clbos_replay_calls": calls,
        "config_b_execution_pass": all(r["full_B_positive"] for r in action_checks),
    }
    if not all(
        r["bound_replay_exact"] and r["full_A_replay_exact"] and r["full_B_positive"]
        for r in action_checks
    ) or not smoke_result["top10_deterministic_replay_pass"] or not smoke_result["clbos_deterministic_replay_pass"]:
        smoke_result["status"] = "FAIL"
    RAW.mkdir(parents=True, exist_ok=True)
    SMOKE.write_text(json.dumps(smoke_result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(smoke_result, indent=2), flush=True)
    if smoke_result["status"] != "PASS":
        raise RuntimeError("Smoke/replay gate failed")


def formal(config_b_binary):
    freeze = json.loads(FREEZE.read_text(encoding="utf-8-sig"))
    if freeze["comparator"]["frozen_k"] != 10 or freeze["comparator"]["k_retuned"]:
        raise RuntimeError("Frozen-K gate failed")
    if not freeze["A1_A4_config_B"]["A1_A4_CONFIG_B_PASS"]:
        raise RuntimeError("Config-B A1-A4 gate failed")
    bounds = load_resolved(
        BOUND_RAW, ["experiment_arm", "field_id", "angle_deg"],
        {"SUCCESS", "INFEASIBLE_NO_SWATHS"},
    )
    fulls = load_resolved(
        FULL_RAW, ["experiment_arm", "field_id", "configuration_id", "angle_deg"],
        {"SUCCESS"},
    )
    results = read_csv(RESULTS)
    t1 = freeze["selection"]["t1_fields"]
    t2 = freeze["selection"]["t2_fields"]
    t3 = freeze["selection"]["t3_fields"]

    angles_1deg = [float(i) for i in range(180)]
    run_arm(t1, "T1", "A_PRIMARY", 1.0, angles_1deg, FULL_A_BIN, bounds, fulls, results)
    run_arm(t2, "T2", "B_MIN_TURN_RADIUS_2P8M", 1.0, angles_1deg, config_b_binary, bounds, fulls, results)

    t1_fail = sum(r["experiment_arm"] == "T1" and r["top10_exact"] != "true" for r in results)
    t2_fail = sum(r["experiment_arm"] == "T2" and r["top10_exact"] != "true" for r in results)
    if t1_fail + t2_fail:
        print(
            "T3_STATUS=NOT_RUN_BY_PRESPECIFIED_EARLY_STOP "
            f"T1_FAILURES={t1_fail} T2_FAILURES={t2_fail}",
            flush=True,
        )
        return

    angles_half = [i / 2.0 for i in range(360)]
    run_arm(t3, "T3", "A_PRIMARY", 0.5, angles_half, FULL_A_BIN, bounds, fulls, results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("smoke", "formal"))
    parser.add_argument("--config-b-binary", required=True, type=Path)
    args = parser.parse_args()
    for path in (MST_BIN, FULL_A_BIN, args.config_b_binary, FREEZE):
        if not path.exists():
            raise RuntimeError(f"Missing dependency: {path}")
    if args.mode == "smoke":
        smoke(args.config_b_binary)
    else:
        formal(args.config_b_binary)


if __name__ == "__main__":
    main()
