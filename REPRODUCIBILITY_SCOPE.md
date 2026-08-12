# Reproducibility scope

## Scientific freeze

- `SCIENTIFIC_METHOD=FROZEN`
- `EMPIRICAL_EVIDENCE=CLOSED`
- `NEW_EXPERIMENT_REQUIRED=false`
- `NEW_EXPERIMENT_COUNT=0`
- `NEW_PLANNER_CALL_COUNT=0`
- `SCIENTIFIC_RESULT_CHANGED=false`

This release is a copy, wrapper, and derived-validation layer. It is not a new scientific authority.

## Level A: analysis-only reproduction

Level A uses only files under `data/` and Python's standard library. It recalculates manuscript-facing counts and descriptive statistics without Route or Path calls. The primary result is `outputs/tables/recomputed_summary.json`.

## Level B: pipeline reproduction

Level B supplies source acquisition, preprocessing, selection, C++ runner/probes, and orchestration code. It requires third-party assets that are not redistributed. Formal execution is manual because it is expensive and environment-sensitive.

## Boundaries

- Candidate domains are the stated finite angular grids.
- CLBOS exactness is certificate-based under the included discrete runner semantics.
- MST-bound admissibility is an analytical manuscript claim under assumptions A1–A4 and exact arithmetic; packaged exhaustive CSV evidence checks floating-point implementation recovery and does not prove that claim.
- Runtime evidence is limited to the recorded three-field microbenchmark.
- The 90-field replay and epsilon sensitivity are post-hoc.
- Oksanen is a matched discrete adaptation.
- DirectDist, degree relaxation, and kinematic/Dubins-MST remain negative/rejected candidates.
- No inference of causal geometry-family effects is supported.

## Public release portability patch

`PUBLIC_RELEASE_PORTABILITY_PATCH=true`. Copied selection CSVs replace developer-local WKT locations with `selected_wkts/<sha256>.wkt`. Copied orchestration scripts read `CLBOS_WORK_ROOT` and `CLBOS_RUNTIME_ROOT`, defaulting to the current work tree and its `.runtime` directory. Scientific constants, candidate grids, objective logic, stopping rules, and result data are unchanged.
