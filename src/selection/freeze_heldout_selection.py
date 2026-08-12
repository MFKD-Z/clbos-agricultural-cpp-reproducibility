#!/usr/bin/env python3
import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("CLBOS_WORK_ROOT", str(Path.cwd()))).resolve()
CACHE = Path(os.environ.get("CLBOS_RUNTIME_ROOT", str(ROOT / ".runtime"))).resolve()

INVENTORY = ROOT / "canary/field_inventory.csv"
PRIOR_FILES = [
    ROOT / "canary/selected_fields.csv",
    ROOT / "bdaos_dense_p0/selected_fresh_fields.csv",
    ROOT / "clbos01_fresh_12_validation/selected_fresh_12_fields.csv",
    ROOT / "clbos01_expanded_30_validation/selected_expanded_30_fields.csv",
]

OUT = ROOT / "clbos01_heldout_topk"
OUT.mkdir(exist_ok=True)
SELECTED = OUT / "selected_heldout_fields.csv"
SNAPSHOT = OUT / "selection_snapshot.txt"

FAMILIES = [
    "CONVEX_NO_HOLES",
    "NONCONVEX_NO_HOLES",
    "HAS_HOLES_OR_INTERNAL_OBSTACLES",
]

TARGET_PER_FAMILY = 30
MIN_ACCEPTABLE_PER_FAMILY = 20  # engineering floor only; not a scientific threshold


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def midpoint_rank_picks(candidates, k):
    candidates = sorted(
        candidates,
        key=lambda r: (float(r["area_m2"]), r["source_path"]),
    )
    n = len(candidates)
    if n < k:
        raise RuntimeError(f"Need >= {k} candidates, got {n}")
    idx = [
        min(n - 1, int(((2 * i + 1) * n) / (2.0 * k)))
        for i in range(k)
    ]
    if len(set(idx)) != k:
        raise RuntimeError(f"Non-unique rank-bin indices for n={n}, k={k}")
    return [(i + 1, j, candidates[j]) for i, j in enumerate(idx)]


def main():
    if not INVENTORY.exists():
        raise RuntimeError(f"Missing inventory: {INVENTORY}")
    for p in PRIOR_FILES:
        if not p.exists():
            raise RuntimeError(f"Missing prior-selection file: {p}")

    prior_rows = []
    for p in PRIOR_FILES:
        prior_rows.extend(read_csv(p))

    excluded_sha = {r["source_wkt_sha256"] for r in prior_rows}
    inventory = read_csv(INVENTORY)

    # Deduplicate exact geometry identities inside the remaining inventory.
    unique = {}
    for r in sorted(inventory, key=lambda x: x["source_path"]):
        sha = r["source_wkt_sha256"]
        if sha in excluded_sha:
            continue
        unique.setdefault(sha, r)

    available = defaultdict(list)
    for r in unique.values():
        if r["family"] in FAMILIES:
            available[r["family"]].append(r)

    counts = {f: len(available[f]) for f in FAMILIES}
    per_family = min(TARGET_PER_FAMILY, min(counts.values()))
    if per_family < MIN_ACCEPTABLE_PER_FAMILY:
        raise RuntimeError(
            f"Too few outcome-blind held-out candidates after exclusions: {counts}"
        )

    if SELECTED.exists():
        selected = read_csv(SELECTED)
        expected = 3 * per_family
        if len(selected) != expected:
            raise RuntimeError(
                f"Existing frozen selection has {len(selected)} rows; "
                f"current outcome-blind rule implies {expected}. Do not overwrite."
            )
        print("=== REUSE FROZEN HELD-OUT SELECTION ===")
    else:
        selected = []
        for family in FAMILIES:
            picks = midpoint_rank_picks(available[family], per_family)
            for rank_bin, idx, src in picks:
                r = dict(src)
                local = CACHE / "selected_wkts" / (r["source_wkt_sha256"] + ".wkt")
                if not local.exists():
                    raise RuntimeError(
                        f"Selected metric WKT missing; do not substitute: {local}"
                    )
                r["field_id"] = f"HOLD_{family}_{rank_bin:02d}"
                r["local_wkt_path"] = str(local)
                r["selection_rule"] = (
                    f"AREA_RANK_{per_family}BIN_MIDPOINT_AFTER_ALL_PRIOR_EXCLUSION"
                )
                r["selection_index_zero_based"] = str(idx)
                r["family_candidate_count_after_exclusion"] = str(len(available[family]))
                selected.append(r)

        fields = [
            "field_id","family","area_m2","source_path","source_wkt_sha256",
            "local_wkt_path","selection_rule","selection_index_zero_based",
            "family_candidate_count_after_exclusion",
        ]
        with SELECTED.open("x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in selected:
                w.writerow({k: r[k] for k in fields})
            f.flush()
            os.fsync(f.fileno())
        print("=== FROZEN HELD-OUT SELECTION CREATED ===")

    c = Counter(r["family"] for r in selected)
    if any(c[f] != per_family for f in FAMILIES):
        raise RuntimeError(f"Family counts invalid: {dict(c)}")

    if any(r["source_wkt_sha256"] in excluded_sha for r in selected):
        raise RuntimeError("Held-out overlap with prior selections detected")

    lines = [
        "CLBOS01 HELD-OUT TOP-K SELECTION SNAPSHOT",
        "",
        "Selection uses geometry metadata only. No FullPlanner, Top-K, regret,",
        "oracle rank, CLBOS call count, or downstream outcome is read.",
        "",
        f"Prior selected unique SHA excluded: {len(excluded_sha)}",
        f"Remaining exact-SHA-unique family counts: {counts}",
        f"Selected per family: {per_family}",
        f"Total held-out fields: {len(selected)}",
        "Rule: deterministic area-rank equal-bin midpoint within each family",
        "after excluding all previously selected geometry SHA identities.",
        "",
    ]
    for f in FAMILIES:
        areas = sorted(float(r["area_m2"]) for r in selected if r["family"] == f)
        lines.append(
            f"{f}: n={len(areas)} area_min={min(areas):.3f} "
            f"area_median={areas[len(areas)//2]:.3f} area_max={max(areas):.3f}"
        )

    SNAPSHOT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(SNAPSHOT.read_text(encoding="utf-8"))
    print("FROZEN_SELECTION =", SELECTED)


if __name__ == "__main__":
    main()
