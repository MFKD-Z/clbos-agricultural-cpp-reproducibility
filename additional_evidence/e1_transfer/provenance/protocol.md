# E1 preregistration freeze

## Identity and timing

- `TASK=CLBOS_E1_FROZEN_K_TRANSFER_KILL_TEST`
- `FREEZE_TIMESTAMP=2026-08-12T21:25:53.6776337+08:00`
- `FREEZE_CORE_SHA256=67c1dfae20edf5737370c054a6fda214349aa019c6fe8d58aa25662448d484d0`
- `USER_PROTOCOL_SHA256=79126587ac97471098d310b0e1ebe6d2c69f5f340465cd792e6099f1225778b3`
- `FROZEN_BEFORE_NEW_DOWNSTREAM_OUTCOME=true`

The scientific question is whether the fixed budget `K=10`, calibrated on the original 90-field 1° benchmark, recovers the complete Route+Path finite-domain optimum in pre-specified outcome-blind field and vehicle/planning transfers, while frozen CLBOS-MST recovers that same optimum by an instance-specific certificate.

## Authority and dependency gate

- Scientific authority: frozen internal raw-result chain under `<original project workspace>`.
- The public reproducibility package is a path-sanitized secondary copy and explicitly is not a replacement scientific authority.
- `DEPENDENCY_CLOSURE_PASS=true`
- `LIFECYCLE_CONFLICT_COUNT=0`
- `MISSING_REAL_INPUT_COUNT=0`
- `AUTHORITY_DUPLICATION_RISK=LOW`
- Fields2Cover commit: `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426` (clean checkout).
- Source input closure: 350 source WKT files; 349 usable inventory rows with exact source hashes; one preprocessing exclusion (`wkt/nl_field_32.wkt`); 349 projected WKT inputs present.

## Outcome-blind eligible pool

A geometry is eligible only if it is absent by exact source SHA-256 from every development/tuning selection, the manuscript-facing 90-field held-out set, and every discovered project downstream-result field reference. Ambiguous prior generation or inspection is excluded conservatively.

The audit found 57 unique development SHA identities, 90 unique held-out SHA identities, no overlap, and no unmapped real-field reference across 49 downstream-result CSVs. The untouched eligible pool contains 202 unique geometries: 5 `CONVEX_NO_HOLES`, 197 `NONCONVEX_NO_HOLES`, and no remaining `HAS_HOLES_OR_INTERNAL_OBSTACLES`. The row-level decision is frozen in `02_E1_OUTCOME_BLIND_ELIGIBILITY_LEDGER.csv`.

## Frozen comparator and common methods

- `FROZEN_K=10`.
- Source: the minimum fixed-K budget observed to achieve 90/90 exact recovery on the existing primary 90-field 1° benchmark.
- `K_RECALIBRATION=false`, `K_PER_DOMAIN_RETUNING=false`, `K_AFTER_FAILURE_EXPANSION=false`, `K_AFTER_SUCCESS_REDUCTION=false`.
- M1: exhaustive complete Route+Path oracle.
- M2: first 10 candidates under the frozen deterministic SwathLength ordering.
- M3: frozen CLBOS-MST, `epsilon=1e-6 m`.

All three methods share field geometry, Fields2Cover revision, planner configuration, candidate domain, swath generation, route planner, path planner, PathLength objective, failure semantics, tie handling, and numerical tolerance. Primary metrics are exact recovery, absolute excess, relative regret, complete downstream evaluation count, and certificate status. Wall-clock is not an E1 claim.

## Configuration A

- Orientation domain: `0..179°` at `1°`.
- Coverage width / robot width: `2.0 m / 2.0 m`.
- Minimum turning radius: `2.0 m`.
- Headland: fixed total `6.0 m` (`ConstHL 3 m`, trapezoidal decomposition, then `ConstHL 3 m`).
- Swaths: fixed-angle `BruteForce`; ordering objective `SwathLength`.
- Route: `RoutePlannerBase` shortest route.
- Path: `DubinsCurves`; complete objective `PathLength`.
- Per-action timeout: `900 s`.

## Config-B freeze and engineering evidence

Config-B changes exactly one factor: minimum turning radius from `2.0 m` to `2.8 m`; every other Configuration-A parameter remains identical. The 2.8 m value is the official John Deere 3033R turning radius without brakes. Fields2Cover documents `setMinTurningRadius` as the robot minimum-radius / maximum-curvature parameter used by path planning.

- Configuration ID: `B_MIN_TURN_RADIUS_2P8M`.
- Engineering source: [John Deere 3033R official specifications](https://www.deere.com/en/tractors/compact-tractors/3-series-compact-tractors/3033r/).
- Parameter semantics: [Fields2Cover robot documentation](https://fields2cover.github.io/source/tutorials/basic_types.html) and [path-planning documentation](https://fields2cover.github.io/source/tutorials/path_planning.html).
- Rationale: a manufacturer-grounded 40% increase represents a less maneuverable but plausible compact agricultural tractor while isolating one vehicle-geometry factor.
- `CONFIG_B_GROUNDED=true`
- `CONFIG_B_FROZEN_BEFORE_OUTCOME=true`
- `CONFIG_B_PARAMETER_GRID_SEARCH=false`

Pinned-source A1–A4 audit:

- `A1_SWATH_PRESERVATION=PASS`: turning radius is consumed only in path planning; geometry, headland, decomposition, coverage width, and swath generation are unchanged.
- `A2_ENDPOINT_CONNECTED_TRANSITIONS=PASS`: `PathPlanning` passes swath end/start poses to `TurningBase::createTurn`; the Dubins path is corrected to the requested endpoints.
- `A3_CONTINUOUS_CONNECTED_TRAVERSAL=PASS`: swaths and Dubins transitions are concatenated in route order; a positive radius changes curvature, not connection semantics.
- `A4_NONNEGATIVE_PATH_DECOMPOSITION=PASS`: `Path::length` sums `fabs(state.len)` and swath/transition segment lengths are nonnegative.
- `ASSUMPTION_SEMANTICS_UNCHANGED=true`
- `A1_A4_CONFIG_B_PASS=true`

## Frozen field selection

For each source geometry family, target counts are allocated by proportional largest remainder, retaining at least one geometry from every nonempty family when feasible. Within a family, candidates are sorted by `(area_m2, source_path)` and selected at deterministic equal-area-rank-bin midpoints. No downstream value enters selection.

- T1: 60 fields from the 202-field eligible pool: 1 convex and 59 nonconvex.
- T2: 30 fields preselected from T1: 1 convex and 29 nonconvex.
- T3: 24 fields preselected from T1: 1 convex and 23 nonconvex.
- T2 and T3 subsets are frozen before any T1/T2 outcome inspection.
- Exact field identities and hashes are in `03_E1_SELECTION_AND_CONFIG_FREEZE.json`.

## T3 trigger

T3 is authorized only when `T1_TOP10_FAILURE_COUNT=0 AND T2_TOP10_FAILURE_COUNT=0`. If either count is positive, T3 is not run and the early-stop reason is `PRESPECIFIED_TRANSFER_FAILURE_ALREADY_OBSERVED`. If authorized, T3 uses `0..179.5°` at `0.5°`, retains Configuration A, and keeps `K=10`.

## Failure, exactness, and tie semantics

- A planner return explicitly identified as `no swaths generated` is model-infeasible for that orientation.
- Timeout, nonzero process exit, malformed output, missing output, or any other unresolved exception is an execution failure, not infeasibility, and prevents a resolved oracle/certificate row.
- Exactness uses the frozen manuscript convention: relative regret `<=1e-9`, with deterministic lower-angle tie-breaking after the frozen SwathLength order.
- The exhaustive oracle is the minimum resolved complete PathLength over the entire finite candidate domain; all unresolved execution failures remain visible.
- A non-exact CLBOS result is retained and immediately triggers `E1_SCIENTIFIC_ANOMALY=true`; no silent retry, method change, or rescue run is allowed.

## Frozen outcome classes

- A: at least one frozen Top-10 failure in a pre-specified executed domain and certified-exact CLBOS recovery: `A_STRONG_TRANSFER_LIMITATION`.
- B: Top-10 exact everywhere, but retrospective perfect-recovery minimum K varies materially by domain: `B_DOMAIN_DEPENDENT_CALIBRATION`.
- C: Top-10 exact everywhere, cheaper than CLBOS, and no material calibration variation: `C_FIXED_K_REMAINS_STRONG`; practical-necessity downgrade required.
- D: CLBOS fails to recover the finite-domain oracle under satisfied assumptions: `D_CLBOS_ANOMALY`.

Retrospective K is descriptive only, is not a method, cannot replace frozen K=10, and cannot trigger selection or reruns.

## Prohibited adaptations

No K retuning, new fields, replacement subset, additional configuration, post-outcome resolution change, bound/stopping-rule/epsilon change, method-name change, continuous-angle optimization, runtime expansion, E2/E3 work, manuscript/figure edit, or public-release modification is authorized.
