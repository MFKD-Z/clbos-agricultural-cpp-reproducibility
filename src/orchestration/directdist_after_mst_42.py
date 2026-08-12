#!/usr/bin/env python3
import csv
import json
import os
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
BIN = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve() / "Fields2Cover-build/agri_f2c_bound_probe"

MST_DIR = ROOT / "clbos01_mst_hierarchical_42"
MST_ACTIONS = MST_DIR / "mst_actions.csv"

FRESH_SEL = ROOT / "clbos01_fresh_12_validation/selected_fresh_12_fields.csv"
EXP_SEL = ROOT / "clbos01_expanded_30_validation/selected_expanded_30_fields.csv"

OUT = ROOT / "clbos01_directdist_after_mst_42"
OUT.mkdir(exist_ok=True)

ACTIONS = OUT / "direct_actions.csv"
FIELD_SUMMARY = OUT / "field_summary.csv"
OVERALL = OUT / "overall_summary.csv"
SNAPSHOT = OUT / "decision_snapshot.txt"

EPS = 1e-6
TOL = 1e-6
TIMEOUT = 900


def read_csv(path):
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def atomic_csv(path, rows):
    keys, seen = [], set()
    for row in rows:
        for k in row:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def append_csv(path, fields, row):
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def load_selected():
    out = {}
    for path in [FRESH_SEL, EXP_SEL]:
        for r in read_csv(path):
            out[r["field_id"]] = r
    if len(out) != 42:
        raise RuntimeError(f"Expected 42 selected fields, got {len(out)}")
    return out


def load_mst_survivors():
    rows = read_csv(MST_ACTIONS)
    success = [r for r in rows if r["status"] == "SUCCESS"]

    by_field = defaultdict(list)
    for r in success:
        by_field[r["field_id"]].append(r)

    survivors = []
    field_jstar = {}

    for fid, rr in by_field.items():
        jstar = min(float(r["oracle_complete_path_length_m"]) for r in rr)
        field_jstar[fid] = jstar
        for r in rr:
            if float(r["mst_total_lb_m"]) < jstar + EPS:
                survivors.append({
                    "field_id": fid,
                    "family": r["family"],
                    "angle_deg": int(r["angle_deg"]),
                    "mst_total_lb_m": float(r["mst_total_lb_m"]),
                    "j_star_m": jstar,
                    "oracle_j_m": float(r["oracle_complete_path_length_m"]),
                })

    survivors.sort(key=lambda x: (x["field_id"], x["angle_deg"]))
    return survivors, field_jstar


def main():
    if not BIN.exists():
        raise RuntimeError(
            f"Missing {BIN}. Build agri_f2c_bound_probe from the earlier stronger-bound P0 first."
        )

    selected = load_selected()
    survivors, field_jstar = load_mst_survivors()

    print(f"MST_SURVIVOR_ACTIONS={len(survivors)}", flush=True)
    if len(survivors) != 180:
        print(
            f"NOTE: expected 180 from the current 42-field summary, observed {len(survivors)}.",
            flush=True,
        )

    fields = [
        "field_id","family","angle_deg",
        "mst_total_lb_m","j_star_m","oracle_j_m",
        "swath_total_length_m","probe_mst_total_lb_m",
        "route_direct_length_m","probe_complete_path_length_m",
        "mst_matches_prior","j_matches_oracle",
        "mst_le_direct","direct_le_j",
        "direct_survives_certificate",
        "upstream_seconds","mst_seconds","route_seconds",
        "direct_seconds","path_seconds","probe_total_seconds",
        "status","error",
    ]

    done = {}
    if ACTIONS.exists():
        for r in read_csv(ACTIONS):
            if r["status"] == "SUCCESS":
                done[(r["field_id"], int(r["angle_deg"]))] = r

    total = len(survivors)
    for i, item in enumerate(survivors, 1):
        key = (item["field_id"], item["angle_deg"])
        if key in done:
            print(
                f"[{i}/{total}] {item['field_id']} angle={item['angle_deg']} RESUME_SKIP",
                flush=True,
            )
            continue

        meta = selected[item["field_id"]]
        try:
            p = subprocess.run(
                [
                    str(BIN),
                    "--wkt-file", meta["local_wkt_path"],
                    "--angle-deg", str(item["angle_deg"]),
                    "--probe-bounds",
                ],
                text=True,
                capture_output=True,
                timeout=TIMEOUT,
            )
            if p.returncode != 0:
                row = {
                    **item,
                    "status": "FAILED",
                    "error": p.stderr.strip(),
                }
            else:
                d = json.loads(p.stdout)
                probe_mst = float(d["mst_total_lb_m"])
                direct = float(d["route_direct_length_m"])
                probe_j = float(d["complete_path_length_m"])
                row = {
                    **item,
                    "swath_total_length_m": f"{float(d['swath_total_length_m']):.12f}",
                    "probe_mst_total_lb_m": f"{probe_mst:.12f}",
                    "route_direct_length_m": f"{direct:.12f}",
                    "probe_complete_path_length_m": f"{probe_j:.12f}",
                    "mst_matches_prior": abs(probe_mst - item["mst_total_lb_m"]) <= TOL,
                    "j_matches_oracle": abs(probe_j - item["oracle_j_m"]) <= TOL,
                    "mst_le_direct": probe_mst <= direct + TOL,
                    "direct_le_j": direct <= probe_j + TOL,
                    "direct_survives_certificate": direct < item["j_star_m"] + EPS,
                    "upstream_seconds": d["upstream_seconds"],
                    "mst_seconds": d["mst_seconds"],
                    "route_seconds": d["route_seconds"],
                    "direct_seconds": d["direct_seconds"],
                    "path_seconds": d["path_seconds"],
                    "probe_total_seconds": d["probe_total_seconds"],
                    "status": "SUCCESS",
                    "error": "",
                }
        except Exception as e:
            row = {
                **item,
                "status": "DRIVER_ERROR",
                "error": repr(e),
            }

        append_csv(ACTIONS, fields, row)
        print(
            f"[{i}/{total}] {item['field_id']} angle={item['angle_deg']} "
            f"{row['status']} {row.get('error','')[:100]}",
            flush=True,
        )
        if row["status"] == "SUCCESS":
            done[key] = row

    # Keep last successful result per intended survivor.
    action_rows = read_csv(ACTIONS)
    latest = {}
    for r in action_rows:
        if r["status"] == "SUCCESS":
            latest[(r["field_id"], int(r["angle_deg"]))] = r

    missing = [
        x for x in survivors
        if (x["field_id"], x["angle_deg"]) not in latest
    ]
    if missing:
        print(f"INCOMPLETE: {len(missing)} intended survivors do not have SUCCESS.", flush=True)

    rows = [
        latest[(x["field_id"], x["angle_deg"])]
        for x in survivors
        if (x["field_id"], x["angle_deg"]) in latest
    ]

    by_field = defaultdict(list)
    for r in rows:
        by_field[r["field_id"]].append(r)

    field_rows = []
    for fid in sorted(selected):
        rr = by_field.get(fid, [])
        expected = [x for x in survivors if x["field_id"] == fid]
        if len(rr) != len(expected):
            field_rows.append({
                "field_id": fid,
                "family": selected[fid]["family"],
                "status": f"INCOMPLETE_{len(rr)}_OF_{len(expected)}",
            })
            continue

        c_mst = len(rr)
        c_direct = sum(
            str(r["direct_survives_certificate"]).lower() == "true"
            for r in rr
        )

        route_sum = sum(float(r["route_seconds"]) for r in rr)
        direct_sum = sum(float(r["direct_seconds"]) for r in rr)
        path_all_sum = sum(float(r["path_seconds"]) for r in rr)
        path_direct_sum = sum(
            float(r["path_seconds"])
            for r in rr
            if str(r["direct_survives_certificate"]).lower() == "true"
        )

        # Under route caching:
        # MST-only downstream work on these candidates = Route + Path for all c_mst.
        # Adding DirectDist = Route + Direct for all c_mst + Path only for c_direct.
        mst_only_downstream = route_sum + path_all_sum
        direct_cascade_downstream = route_sum + direct_sum + path_direct_sum

        field_rows.append({
            "field_id": fid,
            "family": selected[fid]["family"],
            "status": "COMPLETE",
            "mst_survivor_count": c_mst,
            "direct_survivor_count": c_direct,
            "path_calls_saved_by_direct": c_mst - c_direct,
            "path_call_reduction_vs_mst": (
                f"{(c_mst-c_direct)/c_mst:.12f}" if c_mst else ""
            ),
            "all_mst_matches_prior": all(
                str(r["mst_matches_prior"]).lower()=="true" for r in rr
            ),
            "all_j_matches_oracle": all(
                str(r["j_matches_oracle"]).lower()=="true" for r in rr
            ),
            "all_mst_le_direct": all(
                str(r["mst_le_direct"]).lower()=="true" for r in rr
            ),
            "all_direct_le_j": all(
                str(r["direct_le_j"]).lower()=="true" for r in rr
            ),
            "median_route_seconds": f"{statistics.median(float(r['route_seconds']) for r in rr):.9f}",
            "median_direct_seconds": f"{statistics.median(float(r['direct_seconds']) for r in rr):.9f}",
            "median_path_seconds": f"{statistics.median(float(r['path_seconds']) for r in rr):.9f}",
            "measured_mst_only_downstream_seconds": f"{mst_only_downstream:.9f}",
            "cached_direct_cascade_downstream_seconds": f"{direct_cascade_downstream:.9f}",
            "cached_direct_runtime_reduction_vs_mst": (
                f"{1-direct_cascade_downstream/mst_only_downstream:.12f}"
                if mst_only_downstream > 0 else ""
            ),
        })

    atomic_csv(FIELD_SUMMARY, field_rows)

    complete_fields = [r for r in field_rows if r["status"] == "COMPLETE"]
    if len(rows) == len(survivors) and complete_fields:
        c_mst_total = sum(int(r["mst_survivor_count"]) for r in complete_fields)
        c_direct_total = sum(int(r["direct_survivor_count"]) for r in complete_fields)

        route_sum = sum(float(r["route_seconds"]) for r in rows)
        direct_sum = sum(float(r["direct_seconds"]) for r in rows)
        path_all_sum = sum(float(r["path_seconds"]) for r in rows)
        path_direct_sum = sum(
            float(r["path_seconds"])
            for r in rows
            if str(r["direct_survives_certificate"]).lower()=="true"
        )
        mst_only_downstream = route_sum + path_all_sum
        direct_cascade_downstream = route_sum + direct_sum + path_direct_sum

        overall = [{
            "field_count": len(complete_fields),
            "route_direct_actions": len(rows),
            "all_mst_matches_prior": all(
                str(r["mst_matches_prior"]).lower()=="true" for r in rows
            ),
            "all_j_matches_oracle": all(
                str(r["j_matches_oracle"]).lower()=="true" for r in rows
            ),
            "all_mst_le_direct": all(
                str(r["mst_le_direct"]).lower()=="true" for r in rows
            ),
            "all_direct_le_j": all(
                str(r["direct_le_j"]).lower()=="true" for r in rows
            ),
            "mst_stage_path_calls": c_mst_total,
            "direct_stage_path_calls": c_direct_total,
            "path_calls_saved_by_direct": c_mst_total - c_direct_total,
            "path_call_reduction_vs_mst": 1 - c_direct_total/c_mst_total,
            "median_mst_survivor_count": statistics.median(
                int(r["mst_survivor_count"]) for r in complete_fields
            ),
            "median_direct_survivor_count": statistics.median(
                int(r["direct_survivor_count"]) for r in complete_fields
            ),
            "worst_direct_survivor_count": max(
                int(r["direct_survivor_count"]) for r in complete_fields
            ),
            "median_route_seconds_per_action": statistics.median(
                float(r["route_seconds"]) for r in rows
            ),
            "median_direct_seconds_per_action": statistics.median(
                float(r["direct_seconds"]) for r in rows
            ),
            "median_path_seconds_per_action": statistics.median(
                float(r["path_seconds"]) for r in rows
            ),
            "measured_route_seconds_total": route_sum,
            "measured_direct_seconds_total": direct_sum,
            "measured_path_seconds_if_mst_only_total": path_all_sum,
            "measured_path_seconds_with_direct_total": path_direct_sum,
            "measured_mst_only_downstream_seconds": mst_only_downstream,
            "cached_direct_cascade_downstream_seconds": direct_cascade_downstream,
            "cached_direct_runtime_reduction_vs_mst": (
                1-direct_cascade_downstream/mst_only_downstream
            ),
        }]
        atomic_csv(OVERALL, overall)
    else:
        overall = []

    print("\n=== DIRECTDIST AFTER MST: 42-FIELD DIAGNOSTIC ===")
    for r in field_rows:
        if r["status"] != "COMPLETE":
            print(r["field_id"], r["status"])
            continue
        print(
            f"{r['field_id']}: Path calls "
            f"{r['mst_survivor_count']}->{r['direct_survivor_count']} "
            f"saved={r['path_calls_saved_by_direct']} "
            f"cached_runtime_red={100*float(r['cached_direct_runtime_reduction_vs_mst']):.2f}% "
            f"chain={r['all_mst_le_direct']}/{r['all_direct_le_j']}"
        )

    if overall:
        o = overall[0]
        print(
            "\nOVERALL "
            f"ACTIONS={o['route_direct_actions']} "
            f"MST_LE_DIRECT={o['all_mst_le_direct']} "
            f"DIRECT_LE_J={o['all_direct_le_j']} "
            f"J_MATCH={o['all_j_matches_oracle']} "
            f"PATH_CALLS={o['mst_stage_path_calls']}->{o['direct_stage_path_calls']} "
            f"SAVED={o['path_calls_saved_by_direct']} "
            f"PATH_REDUCTION={100*float(o['path_call_reduction_vs_mst']):.1f}% "
            f"MEDIAN_SURVIVORS={o['median_mst_survivor_count']}->{o['median_direct_survivor_count']} "
            f"WORST_DIRECT={o['worst_direct_survivor_count']} "
            f"CACHED_RUNTIME_REDUCTION={100*float(o['cached_direct_runtime_reduction_vs_mst']):.2f}%"
        )

        lines = [
            "CLBOS01 DIRECTDIST-AFTER-MST DECISION SNAPSHOT",
            "",
            f"Route/Direct actions evaluated: {o['route_direct_actions']}",
            f"MST <= Direct on all evaluated actions: {o['all_mst_le_direct']}",
            f"Direct <= J on all evaluated actions: {o['all_direct_le_j']}",
            f"Probe J matches stored Oracle: {o['all_j_matches_oracle']}",
            f"Path calls: {o['mst_stage_path_calls']} -> {o['direct_stage_path_calls']}",
            f"Path calls saved: {o['path_calls_saved_by_direct']}",
            f"Path-call reduction vs MST-only: {100*float(o['path_call_reduction_vs_mst']):.2f}%",
            f"Median field survivors: {o['median_mst_survivor_count']} -> {o['median_direct_survivor_count']}",
            f"Worst Direct survivor count: {o['worst_direct_survivor_count']}",
            f"Cached-route downstream runtime reduction vs MST-only: {100*float(o['cached_direct_runtime_reduction_vs_mst']):.2f}%",
            "",
            "Interpretation rule:",
            "- Strong path-call reduction + positive cached runtime reduction: retain DirectDist as a third stage.",
            "- Strong path-call reduction but near-zero runtime reduction: keep as ablation/analysis, not the main runtime claim.",
            "- Any Direct > J or MST > Direct violation: do not use it as a certified bound until formally resolved.",
        ]
        SNAPSHOT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n" + SNAPSHOT.read_text(encoding="utf-8"))

    print("Outputs:", OUT)


if __name__ == "__main__":
    main()
