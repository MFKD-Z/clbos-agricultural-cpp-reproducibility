# Claim-to-evidence map — v2.0.0

| Manuscript claim group | Public evidence | Reproduction entry |
|---|---|---|
| 350 source / 349 usable / one preprocessing exclusion | `data/provenance/field_inventory.csv`, `field_exclusions.csv` | `scripts/reproduce_numbers.py` |
| Outcome-independent 90-field 30/30/30 held-out selection | held-out/development selection metadata + `src/selection/` | `scripts/reproduce_numbers.py` |
| 65/90 upstream/downstream alignment and 25 disjoint argmin sets | `data/derived/cross_stage/` | `scripts/reproduce_numbers.py` |
| Fixed Top-K 65/80/85/89/90 on original 90 fields | `data/derived/cross_stage/topk_field_results.csv` | `scripts/reproduce_numbers.py` |
| 42-field MST tightening 259 → 180 | `data/derived/mst42/mst_actions.csv` | `scripts/reproduce_numbers.py` |
| Anytime certificate results | `data/derived/anytime/field_budget_results.csv` | `scripts/reproduce_numbers.py` |
| 90-field retrospective tightening / certification-effort distribution | `data/derived/cross_stage/bound_1deg.csv`, field results | `scripts/reproduce_numbers.py` |
| Fixed Top-10 transfer 60/60, 30/30, 24/24; retrospective Kmin 6/3/8 | `additional_evidence/e1_transfer/data/transfer_results.csv` | `scripts/reproduce_v2_added.py` |
| Controlled 2.0 m → 2.8 m turning-radius sensitivity | `additional_evidence/e2_vehicle_sensitivity/data/paired_turn_radius_analysis.csv` | `scripts/reproduce_v2_added.py` |
| Negative 60-field field-difficulty mechanism analysis | `additional_evidence/e2_secondary_mechanism/data/t1_field_metrics.csv` | `scripts/reproduce_v2_added.py` |
| 18-field × five-repeat runtime results | `additional_evidence/e3_runtime/data/runtime_runs.csv`, `field_runtime_summary.csv` | `scripts/reproduce_v2_added.py` |
| Runtime environment and exact external revision | `additional_evidence/e3_runtime/system_snapshot.txt`, `THIRD_PARTY.md` | direct provenance |
| MST admissibility | Analytical proposition/theorem in the associated manuscript under A1–A4 and exact arithmetic | analytical claim, not established by an empirical CSV |
| Rejected bounds / numerical guard | `data/derived/appendix/` | `scripts/reproduce_numbers.py` |

The source snapshots under `additional_evidence/provenance_source_snapshots/`
are traceability artefacts for the executed E1/E2/E3 scripts; they are not the
supported portable Level-A entry point.
