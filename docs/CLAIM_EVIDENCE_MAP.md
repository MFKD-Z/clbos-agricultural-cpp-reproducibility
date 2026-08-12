# Claim-to-evidence map

The machine-readable authority is `REPRO_EVIDENCE_MAP.csv`. The table below summarizes the minimal closure.

| Claim group | Bottom-level public evidence | Recomputed output |
|---|---|---|
| 350 source / 349 usable / one exclusion | `data/provenance/field_inventory.csv`, `field_exclusions.csv` | `dataset_and_selection.csv` |
| Outcome-blind 90-field 30/30/30 held-out set | inventory, development manifests, held-out manifest, selection code | `dataset_and_selection.csv` |
| 65 aligned / 25 disjoint; C2F and Oksanen | 1° bounds, full evaluations, competitor diagnosis, Oksanen result/trace, tie-aware rows | `cross_stage.csv` |
| Top-K 65/80/85/89/90 and rank-8 miss | Top-K field rows and boundary-tie audit | `topk.csv` |
| 42-field MST tightening / oracle-matched empirical recovery (259 to 180) | `mst_actions.csv` | `mst42_field_recomputed.csv` |
| MST admissibility | Analytical proposition/theorem under assumptions A1–A4 and exact arithmetic in the associated manuscript | Not an empirical claim; no CSV establishes it |
| Anytime table | `field_budget_results.csv` | `anytime_recomputed.csv` |
| 90-field 2057 to 1428, hard tail, family totals | 1° bound rows and field results | `replay90_field_recomputed.csv` |
| Runtime microbenchmark | 120 repeat-level runtime rows and system snapshot | `runtime_recomputed.csv` |
| Epsilon and rejected candidates | epsilon field rows, degree/direct/kinematic action rows | `appendix_recomputed.csv` and summary JSON |

Deleting any listed row-level source would prevent an independent field/orientation-level recalculation or provenance check. Precomputed manuscript summaries, old result copies, logs, backups, and superseded runtime tables are therefore excluded.
