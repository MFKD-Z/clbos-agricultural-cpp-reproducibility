#!/usr/bin/env python3
"""Recompute manuscript-facing aggregates from packaged row-level evidence only."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs" / "tables"
EPS = 1e-6


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def truth(value: object) -> bool:
    return str(value).strip().lower() == "true"


def percentile(values: list[float], q: float) -> float:
    xs = sorted(float(value) for value in values)
    if not xs:
        return math.nan
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def dataset_and_selection() -> tuple[dict[str, object], list[dict[str, object]]]:
    inventory = read_csv(DATA / "provenance" / "field_inventory.csv")
    exclusions = read_csv(DATA / "provenance" / "field_exclusions.csv")
    heldout = read_csv(DATA / "heldout" / "selected_heldout_fields.csv")
    development_files = sorted((DATA / "development").glob("*.csv"))
    development = [row for path in development_files for row in read_csv(path)]
    families = Counter(row["family"] for row in heldout)
    inventory_by_source = {row["source_path"]: row for row in inventory}
    heldout_sources = {row["source_path"] for row in heldout}
    development_sources = {row["source_path"] for row in development}
    source_hash_mismatches = sum(
        row["source_path"] not in inventory_by_source
        or inventory_by_source[row["source_path"]]["source_wkt_sha256"] != row["source_wkt_sha256"]
        for row in heldout
    )
    result = {
        "source_wkt_count": len(inventory) + len(exclusions),
        "usable_prepared_inventory_count": len(inventory),
        "preprocessing_exclusion_count": len(exclusions),
        "heldout_field_count": len(heldout),
        "heldout_family_counts": dict(sorted(families.items())),
        "heldout_source_sha_unique_count": len({row["source_wkt_sha256"] for row in heldout}),
        "development_source_count": len(development_sources),
        "heldout_overlap_with_development_count": len(heldout_sources & development_sources),
        "heldout_inventory_sha_mismatch_count": source_hash_mismatches,
    }
    rows = [
        {"metric": "source_wkt_count", "value": result["source_wkt_count"]},
        {"metric": "usable_prepared_inventory_count", "value": len(inventory)},
        {"metric": "preprocessing_exclusion_count", "value": len(exclusions)},
        {"metric": "heldout_field_count", "value": len(heldout)},
        {"metric": "heldout_overlap_with_development_count", "value": len(heldout_sources & development_sources)},
        {"metric": "heldout_inventory_sha_mismatch_count", "value": source_hash_mismatches},
    ]
    rows.extend(
        {"metric": f"heldout_{family}", "value": count}
        for family, count in sorted(families.items())
    )
    return result, rows


def cross_stage() -> tuple[dict[str, object], list[dict[str, object]]]:
    diagnosis = read_csv(DATA / "derived" / "cross_stage" / "competitor_diagnosis.csv")
    by_method: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in diagnosis:
        by_method[row["method"]].append(row)

    rows: list[dict[str, object]] = []
    result: dict[str, object] = {}
    for method in ("BF", "C2F", "OKSANEN_MATCHED"):
        group = by_method[method]
        counts = Counter(row["diagnosis"] for row in group)
        lsw_exact = sum(float(row["lsw_regret"]) <= 1e-9 for row in group)
        j_exact = sum(float(row["j_relative_regret"]) <= 1e-9 for row in group)
        entry = {
            "method": method,
            "field_count": len(group),
            "lsw_exact_count": lsw_exact,
            "j_exact_count": j_exact,
            "pure_cross_stage_mismatch_count": counts["PURE_CROSS_STAGE_OBJECTIVE_MISMATCH"],
            "search_plus_objective_mismatch_count": counts["SEARCH_SCHEDULE_PLUS_OBJECTIVE_MISMATCH"],
            "search_miss_but_j_recovered_count": counts["SEARCH_MISS_BUT_J_RECOVERED"],
        }
        rows.append(entry)
        result[method] = entry

    ties = read_csv(DATA / "derived" / "cross_stage" / "tie_aware_field_results.csv")
    tie_counts = Counter(row["classification"] for row in ties)
    result["tie_aware"] = {
        "field_count": len(ties),
        "aligned": tie_counts["ALIGNED_DETERMINISTIC_BF"],
        "overlapping_upstream_tie": tie_counts["OVERLAPPING_UPSTREAM_TIE_BF_MISS"],
        "disjoint_argmin": tie_counts["DISJOINT_ARGMIN_PURE_MISMATCH"],
        "new_full_calls": sum(int(row["new_full_calls"]) for row in ties),
    }
    return result, rows


def topk() -> tuple[dict[str, object], list[dict[str, object]]]:
    field_rows = read_csv(DATA / "derived" / "cross_stage" / "topk_field_results.csv")
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in field_rows:
        grouped[int(row["k"])].append(row)
    output: list[dict[str, object]] = []
    for k in sorted(grouped):
        group = grouped[k]
        output.append({
            "k": k,
            "field_count": len(group),
            "exact_count": sum(truth(row["exact"]) for row in group),
            "nonzero_regret_count": sum(float(row["regret"]) > 1e-9 for row in group),
            "max_regret": max(float(row["regret"]) for row in group),
            "fixed_full_budget": k,
        })
    audit = read_csv(DATA / "derived" / "cross_stage" / "top5_boundary_tie_audit.csv")
    if len(audit) != 1:
        raise RuntimeError(f"Expected one Top-5 failure audit row, found {len(audit)}")
    failure = audit[0]
    result = {
        "exact_counts": {str(row["k"]): row["exact_count"] for row in output},
        "unique_top5_failure_field": failure["field_id"],
        "unique_top5_failure_oracle_lsw_rank_start": int(failure["oracle_lsw_strict_rank_start"]),
        "unique_top5_failure_oracle_lsw_rank_end": int(failure["oracle_lsw_tie_rank_end"]),
        "unique_top5_failure_tie_dependent": truth(failure["top5_failure_tie_dependent"]),
    }
    return result, output


def mst42() -> tuple[dict[str, object], list[dict[str, object]]]:
    actions = [
        row for row in read_csv(DATA / "derived" / "mst42" / "mst_actions.csv")
        if row["status"] == "SUCCESS"
    ]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in actions:
        grouped[row["field_id"]].append(row)
    field_rows: list[dict[str, object]] = []
    for field_id, group in sorted(grouped.items()):
        jstar = min(float(row["oracle_complete_path_length_m"]) for row in group)
        c_lsw = sum(float(row["swath_total_length_m"]) < jstar + EPS for row in group)
        c_mst = sum(float(row["mst_total_lb_m"]) < jstar + EPS for row in group)
        field_rows.append({
            "field_id": field_id,
            "family": group[0]["family"],
            "feasible_orientation_count": len(group),
            "j_star_m": jstar,
            "lsw_only_full_calls": c_lsw,
            "mst_full_calls": c_mst,
            "mst_admissible_all": all(truth(row["mst_le_j"]) for row in group),
            "nested_lsw_le_mst_all": all(truth(row["lsw_le_mst"]) for row in group),
        })
    result = {
        "field_count": len(field_rows),
        "mst_admissible_fields": sum(row["mst_admissible_all"] for row in field_rows),
        "nested_bound_fields": sum(row["nested_lsw_le_mst_all"] for row in field_rows),
        "lsw_only_total_full_calls": sum(int(row["lsw_only_full_calls"]) for row in field_rows),
        "mst_total_full_calls": sum(int(row["mst_full_calls"]) for row in field_rows),
        "lsw_only_median_full_calls": statistics.median(int(row["lsw_only_full_calls"]) for row in field_rows),
        "mst_median_full_calls": statistics.median(int(row["mst_full_calls"]) for row in field_rows),
    }
    return result, field_rows


def anytime() -> tuple[dict[str, object], list[dict[str, object]]]:
    source = read_csv(DATA / "derived" / "anytime" / "field_budget_results.csv")
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in source:
        grouped[(row["bound"], int(row["budget_full_calls"]))].append(row)
    output: list[dict[str, object]] = []
    for (bound, budget), group in sorted(grouped.items()):
        output.append({
            "bound": bound,
            "budget_full_calls": budget,
            "field_count": len(group),
            "empirical_exact_fields": sum(truth(row["empirical_exact"]) for row in group),
            "certified_exact_fields": sum(truth(row["certified_exact_conservative"]) for row in group),
            "median_empirical_regret": statistics.median(float(row["empirical_regret"]) for row in group),
            "max_empirical_regret": max(float(row["empirical_regret"]) for row in group),
            "median_certified_gap": statistics.median(float(row["certified_relative_gap"]) for row in group),
            "max_certified_gap": max(float(row["certified_relative_gap"]) for row in group),
            "certified_within_0p01_fields": sum(truth(row["certified_within_0p01"]) for row in group),
            "certified_within_0p05_fields": sum(truth(row["certified_within_0p05"]) for row in group),
        })
    return {"row_count": len(output), "source_field_budget_rows": len(source)}, output


def replay90() -> tuple[dict[str, object], list[dict[str, object]]]:
    bounds = [
        row for row in read_csv(DATA / "derived" / "cross_stage" / "bound_1deg.csv")
        if row["status"] == "SUCCESS"
    ]
    fields = {
        row["field_id"]: row
        for row in read_csv(DATA / "derived" / "cross_stage" / "field_results.csv")
        if row["status"] == "COMPLETE"
    }
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in bounds:
        grouped[row["field_id"]].append(row)
    rows: list[dict[str, object]] = []
    for field_id, group in sorted(grouped.items()):
        field = fields[field_id]
        jstar = float(field["oracle_j_star_m"])
        lsw_calls = sum(float(row["swath_total_length_m"]) < jstar + EPS for row in group)
        mst_calls = int(field["mst_certified_full_calls"])
        rows.append({
            "field_id": field_id,
            "family": field["family"],
            "feasible_orientation_count": int(field["feasible_orientation_count"]),
            "lsw_only_full_calls": lsw_calls,
            "mst_full_calls": mst_calls,
            "saved_full_calls": lsw_calls - mst_calls,
            "comparison": "improved" if mst_calls < lsw_calls else "equal" if mst_calls == lsw_calls else "worse",
        })
    lsw_total = sum(int(row["lsw_only_full_calls"]) for row in rows)
    mst_total = sum(int(row["mst_full_calls"]) for row in rows)
    calls = [int(row["mst_full_calls"]) for row in rows]
    comparisons = Counter(str(row["comparison"]) for row in rows)
    family_totals = Counter()
    for row in rows:
        family_totals[str(row["family"])] += int(row["mst_full_calls"])
    result = {
        "field_count": len(rows),
        "lsw_only_total_full_calls": lsw_total,
        "mst_total_full_calls": mst_total,
        "saved_full_calls": lsw_total - mst_total,
        "relative_reduction": (lsw_total - mst_total) / lsw_total,
        "improved_fields": comparisons["improved"],
        "equal_fields": comparisons["equal"],
        "worse_fields": comparisons["worse"],
        "mean_full_calls": statistics.mean(calls),
        "p50_full_calls": percentile(calls, 0.50),
        "p90_full_calls": percentile(calls, 0.90),
        "p95_full_calls": percentile(calls, 0.95),
        "max_full_calls": max(calls),
        "family_full_call_totals": dict(sorted(family_totals.items())),
        "oracle_matched_fields": sum(float(row["mst_full_calls"]) >= 1 for row in rows),
    }
    return result, rows


def runtime() -> tuple[dict[str, object], list[dict[str, object]]]:
    source = [
        row for row in read_csv(DATA / "derived" / "runtime" / "runtime_runs.csv")
        if row["status"] == "SUCCESS"
    ]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in source:
        grouped[(row["field_id"], row["resolution"])].append(row)
    detail: list[dict[str, object]] = []
    for (field_id, resolution), group in sorted(grouped.items()):
        h = [float(row["wall_seconds"]) for row in group if row["method"] == "HIERARCHICAL"]
        e = [float(row["wall_seconds"]) for row in group if row["method"] == "EXHAUSTIVE"]
        h_j = [float(row["j_star_m"]) for row in group if row["method"] == "HIERARCHICAL"]
        e_j = [float(row["j_star_m"]) for row in group if row["method"] == "EXHAUSTIVE"]
        if len(h) != 5 or len(e) != 5:
            raise RuntimeError(f"Runtime group {field_id}/{resolution} lacks five repeats per method")
        mh, me = statistics.median(h), statistics.median(e)
        detail.append({
            "field_id": field_id,
            "family": group[0]["family"],
            "resolution": resolution,
            "candidate_count": int(group[0]["candidate_count"]),
            "repeat_count": len(h),
            "exact_objective_match_all_repeats": math.isclose(min(h_j), min(e_j), rel_tol=1e-9),
            "median_hierarchical_seconds": mh,
            "median_exhaustive_seconds": me,
            "field_speedup": me / mh,
            "field_runtime_reduction": 1.0 - mh / me,
            "median_hierarchical_full_calls": statistics.median(int(row["full_calls"]) for row in group if row["method"] == "HIERARCHICAL"),
        })
    order = {"10deg": 0, "5deg": 1, "2p5deg": 2, "1deg": 3}
    summaries: list[dict[str, object]] = []
    for resolution in sorted({str(row["resolution"]) for row in detail}, key=order.get):
        group = [row for row in detail if row["resolution"] == resolution]
        speedups = [float(row["field_speedup"]) for row in group]
        reductions = [float(row["field_runtime_reduction"]) for row in group]
        summaries.append({
            "resolution": resolution,
            "candidate_count": group[0]["candidate_count"],
            "field_count": len(group),
            "repeat_count_per_method_per_field": group[0]["repeat_count"],
            "exact_fields": sum(bool(row["exact_objective_match_all_repeats"]) for row in group),
            "median_field_speedup": statistics.median(speedups),
            "min_field_speedup": min(speedups),
            "max_field_speedup": max(speedups),
            "median_field_runtime_reduction": statistics.median(reductions),
            "min_field_runtime_reduction": min(reductions),
            "max_field_runtime_reduction": max(reductions),
            "median_field_full_calls": statistics.median(float(row["median_hierarchical_full_calls"]) for row in group),
        })
    return {
        "field_count": len({row["field_id"] for row in detail}),
        "repeat_count_per_method_per_field": 5,
        "population_level_claim": False,
        "summary_rows": summaries,
    }, summaries


def appendix() -> tuple[dict[str, object], list[dict[str, object]]]:
    eps_rows = read_csv(DATA / "derived" / "appendix" / "epsilon_sensitivity_field_level.csv")
    eps_grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in eps_rows:
        eps_grouped[row["epsilon_m"]].append(row)
    output: list[dict[str, object]] = []
    for epsilon, group in eps_grouped.items():
        calls = [int(row["full_calls"]) for row in group]
        output.append({
            "analysis": "epsilon_lsw_only_replay",
            "epsilon_m": epsilon,
            "field_count": len(group),
            "exact_recovery_count": sum(truth(row["exact_oracle_recovery"]) for row in group),
            "angle_match_count": sum(truth(row["angle_match"]) for row in group),
            "median_full_calls": statistics.median(calls),
            "mean_full_calls": statistics.mean(calls),
            "worst_case_full_calls": max(calls),
        })

    degree = [row for row in read_csv(DATA / "derived" / "appendix" / "degree_actions.csv") if row["status"] == "SUCCESS"]
    direct = [row for row in read_csv(DATA / "derived" / "appendix" / "direct_actions.csv") if row["status"] == "SUCCESS"]
    kin_fields = read_csv(DATA / "derived" / "appendix" / "kinematic_field_summary.csv")
    hard_kin_fields = [row for row in kin_fields if row["class"] == "HARD"]
    result = {
        "epsilon": {row["epsilon_m"]: row for row in output},
        "degree_relaxation": {
            "action_count": len(degree),
            "all_mst_admissible": all(truth(row["mst_le_j"]) for row in degree),
            "all_degree_admissible": all(truth(row["degree_le_j"]) for row in degree),
            "all_combined_admissible": all(truth(row["combined_le_j"]) for row in degree),
        },
        "direct_distance": {
            "action_count": len(direct),
            "all_mst_matches_prior": all(truth(row["mst_matches_prior"]) for row in direct),
            "all_j_matches_oracle": all(truth(row["j_matches_oracle"]) for row in direct),
            "all_direct_le_j": all(truth(row["direct_le_j"]) for row in direct),
        },
        "kinematic_negative_candidate": {
            "field_count": len(kin_fields),
            "hard_field_count": len(hard_kin_fields),
            "hard_euclidean_total_full_calls": sum(int(row["C_euclidean"]) for row in hard_kin_fields),
            "hard_kinematic_total_full_calls": sum(int(row["C_kinematic"]) for row in hard_kin_fields),
            "all_dominance_euclidean_le_kinematic": all(truth(row["dominance_E_le_D"]) for row in kin_fields),
        },
    }
    return result, output


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dataset, dataset_rows = dataset_and_selection()
    cross, cross_rows = cross_stage()
    topk_result, topk_rows = topk()
    mst_result, mst_rows = mst42()
    anytime_result, anytime_rows = anytime()
    replay_result, replay_rows = replay90()
    runtime_result, runtime_rows = runtime()
    appendix_result, appendix_rows = appendix()

    summary = {
        "provenance": dataset,
        "cross_stage": cross,
        "topk": topk_result,
        "mst_42": mst_result,
        "anytime": anytime_result,
        "replay_90": replay_result,
        "runtime_scope": runtime_result,
        "appendix": appendix_result,
    }
    (OUT / "recomputed_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_csv(OUT / "dataset_and_selection.csv", dataset_rows)
    write_csv(OUT / "cross_stage.csv", cross_rows)
    write_csv(OUT / "topk.csv", topk_rows)
    write_csv(OUT / "mst42_field_recomputed.csv", mst_rows)
    write_csv(OUT / "anytime_recomputed.csv", anytime_rows)
    write_csv(OUT / "replay90_field_recomputed.csv", replay_rows)
    write_csv(OUT / "runtime_recomputed.csv", runtime_rows)
    write_csv(OUT / "appendix_recomputed.csv", appendix_rows)

    print("ANALYSIS_ONLY_REPRODUCTION=PASS")
    print(f"SUMMARY={OUT / 'recomputed_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
