#!/usr/bin/env python3
"""Rebuild the final manuscript Fig. 4 data view from packaged E3 timing evidence.

This is a data-level reproduction of the runtime benefit/cost figure; journal
layout may differ from the manuscript artwork.
"""
from __future__ import annotations
import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "additional_evidence" / "e3_runtime" / "data" / "runtime_runs.csv"
SUMMARY = ROOT / "additional_evidence" / "e3_runtime" / "data" / "field_runtime_summary.csv"
OUT = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

def read_csv(p):
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def main():
    import matplotlib.pyplot as plt

    runs = read_csv(RUNS)
    summary = read_csv(SUMMARY)
    by = defaultdict(float)
    for r in runs:
        if r["status"] == "SUCCESS":
            by[(int(r["repeat"]), r["method"])] += float(r["wall_seconds"])
    vals = defaultdict(list)
    for (rep, method), value in sorted(by.items()):
        vals[method].append(value)

    exhaustive = statistics.median(vals["EXHAUSTIVE"])
    clbos = statistics.median(vals["CLBOS_MST"])
    top10 = statistics.median(vals["TOP10_LSW_PRECOMPUTED"])
    speedup = exhaustive / clbos
    reduction = 100.0 * (1.0 - clbos / exhaustive)
    bound_frac = statistics.median(float(r["median_clbos_bound_fraction"]) for r in summary)
    full_frac = 1.0 - bound_frac
    full_calls = statistics.median(float(r["median_clbos_full_calls"]) for r in summary)
    premium = clbos / top10

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), constrained_layout=True)

    ax = axes[0]
    bars = ax.bar(["Exhaustive", "CLBOS-MST"], [exhaustive, clbos])
    ax.set_ylabel("Aggregate median-repeat wall time (s)")
    ax.set_title("(a) End-to-end runtime")
    ax.bar_label(bars, fmt="%.1f", padding=3)
    ax.text(0.5, max(exhaustive, clbos)*0.82,
            f"{speedup:.2f}× speedup\n{reduction:.2f}% reduction",
            ha="center", va="center")

    ax = axes[1]
    ax.bar(["CLBOS-MST"], [100*bound_frac], label="Bound acquisition")
    ax.bar(["CLBOS-MST"], [100*full_frac], bottom=[100*bound_frac], label="Selected complete evaluations")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Median CLBOS wall-time share (%)")
    ax.set_title("(b) Runtime composition")
    ax.legend(frameon=False, loc="lower center")
    ax.text(0, 50, f"Bound acquisition\n{100*bound_frac:.1f}%", ha="center", va="center")
    ax.text(0, 7, f"Median full calls = {full_calls:g}", ha="center", va="center")
    ax.text(0.98, 0.98,
            f"Favourable Top-10: {top10:.1f} s\nCLBOS/Top-10: {premium:.2f}×\n(non-equal scope)",
            transform=ax.transAxes, ha="right", va="top", fontsize=8)

    for ext in ("png", "pdf"):
        path = OUT / f"figure4_runtime_benefit_cost.{ext}"
        if ext == "png":
            fig.savefig(path, dpi=600, bbox_inches="tight")
        else:
            fig.savefig(path, bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    main()
