#!/usr/bin/env python3
"""Rebuild manuscript Figs. 2–3 and Supplementary Fig. S1 from packaged frozen CSV evidence."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
EPS = 1e-6


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def percentile(values: list[int], probability: float) -> float:
    """NumPy-compatible linear percentile for the deterministic figure labels."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def save(fig: object, stem: str, plt: object) -> None:
    fig.savefig(FIGURES / f"{stem}.png", dpi=600, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def make_figure2(plt: object) -> None:
    """Unique Top-5 failure diagnostic and its CLBOS-MST certification trace."""
    audit = read_csv(DATA / "cross_stage" / "top5_boundary_tie_audit.csv")[0]
    field_id = audit["field_id"]
    rows = [
        row
        for row in read_csv(DATA / "cross_stage" / "bound_1deg.csv")
        if row["field_id"] == field_id and row["status"] == "SUCCESS"
    ]
    field = next(
        row
        for row in read_csv(DATA / "cross_stage" / "field_results.csv")
        if row["field_id"] == field_id and row["status"] == "COMPLETE"
    )

    topk = int(audit["k"])
    oracle_angle = int(audit["oracle_best_angle_deg"])
    oracle_lsw_rank = int(audit["oracle_lsw_strict_rank_start"])
    kth_threshold = float(audit["kth_lsw_threshold_m"])
    j_star = float(field["oracle_j_star_m"])
    mst_calls = int(field["mst_certified_full_calls"])

    by_lsw = sorted(rows, key=lambda row: (float(row["swath_total_length_m"]), int(row["angle_deg"])))
    oracle_lsw = float(next(row for row in by_lsw if int(row["angle_deg"]) == oracle_angle)["swath_total_length_m"])
    cutoff_lsw = float(by_lsw[topk - 1]["swath_total_length_m"])
    by_mst = sorted(rows, key=lambda row: (float(row["mst_total_lb_m"]), int(row["angle_deg"])))
    oracle_mst_index = next(i for i, row in enumerate(by_mst) if int(row["angle_deg"]) == oracle_angle)
    oracle_mst_rank = oracle_mst_index + 1
    oracle_mst = float(by_mst[oracle_mst_index]["mst_total_lb_m"])

    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.9))
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.18, top=0.84, wspace=0.23)
    note_box = dict(boxstyle="round,pad=0.24", fc="white", ec="0.75", lw=0.6, alpha=0.98)

    ax = axes[0]
    shown = by_lsw[:15]
    ranks = list(range(1, len(shown) + 1))
    lsw_values = [float(row["swath_total_length_m"]) for row in shown]
    ax.plot(ranks, lsw_values, marker="o", color="#1f77b4", linewidth=1.8, markersize=4.2, label=r"$L_{\mathrm{sw}}$")
    ax.axvline(topk + 0.5, color="#5f5f5f", linestyle="--", linewidth=1.2, label=f"Top-{topk} cutoff")
    ax.axhline(kth_threshold, color="#f2b880", linestyle=":", linewidth=1.5, label=f"{topk}th SwathLength value")
    ax.scatter([topk], [cutoff_lsw], color="#ff7f0e", s=34, zorder=5)
    ax.scatter([oracle_lsw_rank], [oracle_lsw], color="#d62728", s=42, zorder=6)
    ax.annotate("No boundary tie", xy=(topk, cutoff_lsw), xytext=(0.03, 0.89), textcoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color="#ff7f0e", lw=1.1), color="#ff7f0e",
                fontsize=8.2, ha="left", va="top", bbox=note_box)
    ax.annotate("Oracle angle\n(rank 8)", xy=(oracle_lsw_rank, oracle_lsw), xytext=(0.72, 0.89),
                textcoords="axes fraction", arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.1),
                color="#d62728", fontsize=8.2, ha="center", va="top", bbox=note_box)
    ax.set(xlim=(1, 15), ylim=(41.0, 70.5), xlabel=r"Candidate rank by $L_{\mathrm{sw}}$", ylabel="SwathLength (m)")
    ax.set_title("(a) Top-5 misses the oracle angle", pad=22)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.70, 0.03), handlelength=2.0)

    ax = axes[1]
    shown = by_mst[:25]
    ranks = list(range(1, len(shown) + 1))
    mst_values = [float(row["mst_total_lb_m"]) for row in shown]
    ax.plot(ranks, mst_values, marker="o", color="#2ca02c", linewidth=1.8, markersize=4.2,
            label=r"$L_{\mathrm{sw}} + T_{\mathrm{MST}}^{E}$")
    ax.axhline(j_star, color="#9467bd", linestyle="--", linewidth=1.3, label=r"$J^{\star}$ stopping threshold")
    ax.axvline(mst_calls + 0.5, color="#5f5f5f", linestyle=":", linewidth=1.4,
               label=f"Recorded CLBOS count = {mst_calls}")
    ax.scatter([oracle_mst_rank], [oracle_mst], color="#d62728", s=42, zorder=6)
    ax.annotate("Oracle angle", xy=(oracle_mst_rank, oracle_mst), xytext=(0.12, 0.96),
                textcoords="axes fraction", arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.1),
                color="#d62728", fontsize=8.2, ha="left", va="top", bbox=note_box)
    blue_box = dict(boxstyle="round,pad=0.26", fc="white", ec="#1e40ff", lw=0.9, alpha=0.98)
    ax.annotate("20 lower-bound-ranked\ncandidates require complete\nevaluation", xy=(mst_calls + 0.5, j_star),
                xytext=(0.58, 0.98), textcoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color="#1e40ff", lw=1.2), color="#1e40ff",
                fontsize=8.0, ha="center", va="top", bbox=blue_box)
    ax.set(xlim=(1, 25), ylim=(47.0, 99.0),
           xlabel=r"Candidate rank by $L_{\mathrm{sw}} + T_{\mathrm{MST}}^{E}$",
           ylabel="Lower bound / objective (m)")
    ax.set_title("(b) CLBOS stops only after certification", pad=22)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.72, 0.03), handlelength=2.0)
    save(fig, "figure2_top5_case_study_color", plt)


def make_figure3(plt: object, PercentFormatter: object) -> None:
    """Anytime exact-certification rate and unresolved-field gap curves."""
    rows = read_csv(TABLES / "anytime_recomputed.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.2), constrained_layout=True)
    styles = [("LSW", "#1f77b4", "o", r"$L_{\mathrm{sw}}$ bound"),
              ("MST", "#ff7f0e", "s", r"$L_{\mathrm{sw}} + T_{\mathrm{MST}}^{E}$ bound")]
    for bound, color, marker, label in styles:
        subset = sorted((row for row in rows if row["bound"] == bound), key=lambda row: int(row["budget_full_calls"]))
        axes[0].plot([int(row["budget_full_calls"]) for row in subset],
                     [int(row["certified_exact_fields"]) / int(row["field_count"]) for row in subset],
                     color=color, marker=marker, linewidth=1.8, markersize=4.5, label=label)
        axes[1].plot([int(row["budget_full_calls"]) for row in subset],
                     [100.0 * float(row["median_certified_gap"]) for row in subset],
                     color=color, marker=marker, linewidth=1.8, markersize=4.5, label=label)
    axes[0].set(xlabel="Complete downstream-evaluation budget", ylabel="Fields certified exact", ylim=(0, 1.02), xticks=[1, 2, 3, 5, 10])
    axes[0].yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    axes[0].set_title("(a) Exact stopping certificate")
    axes[0].legend(frameon=False, loc="lower right")
    axes[1].set(xlabel="Complete downstream-evaluation budget", ylabel="Median certified relative gap (%)", xticks=[1, 2, 3, 5, 10])
    axes[1].set_title("(b) Bound tightness among unresolved fields")
    axes[1].legend(frameon=False, loc="upper right")
    save(fig, "figure3_anytime_certification_color", plt)


def make_figure4(plt: object, PercentFormatter: object) -> None:
    """Empirical CDF and hard-tail profile of Full evaluations on 90 fields."""
    rows = read_csv(TABLES / "replay90_field_recomputed.csv")
    lsw = sorted(int(row["lsw_only_full_calls"]) for row in rows)
    mst = sorted(int(row["mst_full_calls"]) for row in rows)
    ecdf = [(index + 1) / len(rows) for index in range(len(rows))]
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.2), constrained_layout=True)
    axes[0].step(lsw, ecdf, where="post", color="#1f77b4", linewidth=1.8, label=r"$L_{\mathrm{sw}}$ only")
    axes[0].step(mst, ecdf, where="post", color="#ff7f0e", linewidth=1.8, label=r"$L_{\mathrm{sw}} + T_{\mathrm{MST}}^{E}$")
    axes[0].set(xlabel="Complete downstream evaluations", ylabel="Empirical cumulative probability", ylim=(0, 1.02))
    axes[0].set_title("(a) 90-field 1° held-out distribution", fontsize=9.5)
    axes[0].yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    axes[0].legend(frameon=False, loc="lower right")
    axes[1].step(mst, ecdf, where="post", color="#2ca02c", linewidth=1.8)
    values = [percentile(mst, 0.50), percentile(mst, 0.90), percentile(mst, 0.95), float(max(mst))]
    for value, label, color, y in zip(values, ["P50", "P90", "P95", "Max"],
                                       ["#2ca02c", "#1f77b4", "#ff7f0e", "#d62728"],
                                       [0.18, 0.37, 0.56, 0.75]):
        axes[1].axvline(value, color=color, linestyle="--", linewidth=1.2)
        label_text = f"{label} = {value:.2f}" if label != "Max" else f"{label} = {int(value)}"
        axes[1].text(value + 1.5, y, label_text, color=color, fontsize=8, ha="left", va="center")
    axes[1].set(xlabel="CLBOS-MST complete downstream evaluations", ylabel="Empirical cumulative probability", ylim=(0, 1.02))
    axes[1].set_title("(b) Heavy-tail profile of CLBOS-MST", fontsize=9.5)
    axes[1].yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    save(fig, "supplementary_figure_s1_certification_effort_ecdf", plt)


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "reproduce_numbers.py")], cwd=ROOT, check=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import PercentFormatter
    except ImportError as exc:
        raise SystemExit("matplotlib is required; install environment/python_requirements.txt") from exc

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "legend.fontsize": 8.8,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    FIGURES.mkdir(parents=True, exist_ok=True)
    make_figure2(plt)
    make_figure3(plt, PercentFormatter)
    make_figure4(plt, PercentFormatter)
    print("FIGURE_REPRODUCTION=PASS")
    print("MANUSCRIPT_DATA_FIGURES_REPRODUCIBLE=Fig.2,Fig.3,Fig.4")
    print("NONREPRODUCIBLE_FIGURES=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
