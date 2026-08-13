# Reproducing the v2-added evidence

This document covers the evidence added after public v1. Core results remain
reproducible with `scripts/reproduce_numbers.py`.

## One-command numerical recalculation

```bash
python3 scripts/reproduce_v2_added.py
```

This standard-library script uses only packaged CSV evidence and performs no
planner calls.

It writes:

- `outputs/tables/v2_added_recomputed.json`
- `outputs/tables/v2_added_recomputed.csv`

## E1 — fixed-K transfer

Primary evidence:

- `additional_evidence/e1_transfer/data/transfer_results.csv`
- `candidate_bounds.csv`
- `candidate_full_paths.csv`

Recomputed manuscript-facing results include:
- original-configuration 1° transfer: Top-10 60/60 exact, CLBOS 60/60 exact;
- turning-radius 2.8 m transfer: Top-10 30/30 exact, CLBOS 30/30 exact;
- original-configuration 0.5° transfer: Top-10 24/24 exact, CLBOS 24/24 exact;
- retrospective sufficient K values 6, 3 and 8;
- CLBOS versus Top-10 complete-evaluation totals for each domain.

## E2 — controlled turning-radius sensitivity

Primary evidence:

`additional_evidence/e2_vehicle_sensitivity/data/paired_turn_radius_analysis.csv`

The recalculation recovers:
- 30 paired fields;
- aggregate complete evaluations 184 → 345;
- 17 increase / 13 unchanged / 0 decrease;
- median paired P90 absolute-gap increase ≈ 565.714 m;
- weak paired gap-effort Spearman association ≈ 0.175.

The result is interpreted as directional aggregate sensitivity, not as a
field-level causal law.

## E2 secondary — 60-field negative mechanism analysis

Primary evidence:

`additional_evidence/e2_secondary_mechanism/data/t1_field_metrics.csv`

The portable recalculation reproduces the reported Spearman associations,
bootstrap interval, adjusted-R² summaries and combined gap coefficient. The
result does not support a simple global P90 relaxation-gap explanation of
field-to-field certification effort.

## E3 — stratified repeated runtime

Primary evidence:

- `additional_evidence/e3_runtime/data/runtime_runs.csv`
- `additional_evidence/e3_runtime/data/field_runtime_summary.csv`

The recalculation recovers:
- 18 fields × five repeats;
- CLBOS exact and faster than exhaustive on all 18 fields;
- median field-level speedup ≈ 7.43×;
- aggregate speedup ≈ 10.51×;
- aggregate runtime reduction ≈ 90.49%;
- median bound-acquisition share ≈ 90.9%;
- median CLBOS complete evaluations = 5;
- observed CLBOS/favourable-Top-10 timing ratio ≈ 5.89×.

The Top-10 timing is deliberately non-equal-scope because ranking acquisition
is omitted.

## Executed-source provenance

Path-sanitized copies of the scripts used to generate E1/E2/E3 are retained in:

`additional_evidence/provenance_source_snapshots/`

They preserve algorithmic/protocol traceability but are not the supported
portable reproduction entry point. The supported package-level numerical
recalculation is `scripts/reproduce_v2_added.py`.
