# S7 pinned planner runtime semantics audit

Run time (Asia/Shanghai): 2026-10-11T18:43:32.999967+08:00. **S7_GATE=FAIL.** A3 fails in 3 of 6 preselected smoke cases at the declared 1e-6 m spatial threshold. The run stopped before the remaining 127 cases, as requested for a genuine failure. This is an empirical finding for executed inputs, not a formal guarantee for all inputs.

## Text and execution identity

`PAPER_TEXT_NOT_AVAILABLE`: no latest JESTECH Section 2.2, Proposition 1, Table 1 or S7 file was found locally. The accessible `submission/CLBOS_BE_FINAL_SUBMISSION_MANUSCRIPT.docx` contains related A1–A4 wording and Proposition 1, but is a Biosystems Engineering file and is not represented here as JESTECH text. The audit uses the four operational definitions in the supplied task document.

Fields2Cover HEAD `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`; source worktree clean=True. Production adapter SHA-256 `348a227182252feb63743fb9cd711fec6dd0a57ce7891b99dda3db4d1ab23658`, identical to the release adapter. Original binary SHA-256 `4c89a57f2ffe4d1bd00f42e7743936297217cb2e91971062eaf61f3046712f4c`; linked `libFields2Cover.so` SHA-256 `1338ade681056f031806bb1349f3a5cd5392e614a00c5fac3170ec7f3574ceda`. New observer binary SHA-256 `fc8490e6614b2796d12b0c7c6370437362778277a8b28694238821e80d7c496d`. Original binary's CMake cache binds `F2C_SOURCE_DIR=<ORIGINAL_CACHE>/Fields2Cover` and `CMAKE_HOME_DIRECTORY=<ORIGINAL_WORKSPACE>/runner`; `ldd` resolves the pinned library in the old build directory. The observer only adds JSON serialization to a copy of the original runner and links that same library. Six baseline replays matched swath count, swath length, and complete path length.

The adapter fixes a 6 m total headland through 3 m + TrapezoidalDecomp + 3 m, uses the same narrow splitByLine fallback, BruteForce swaths, RoutePlannerBase::genRoute, PathPlanning::planPath with DubinsCurves, and PathLength::computeCost. Inputs are metric selected WKT files; source WKT SHA-256 is checked against the frozen selection table. Each metric WKT hash is in `s7_predeclared_cases.json`.

## Source semantics and runtime tests

Source line numbers below refer to `<ORIGINAL_CACHE>/Fields2Cover` at the pinned HEAD.

- `route_planning/route_planner_base.cpp:21-34` constructs shortest/coverage graphs and transforms solver IDs; `:193-227` matches route node endpoints to swaths and appends swaths. This does not independently prove a one-to-one geometry multiset or complete path traversal.
- `path_planning/path_planning.cpp:12-25` concatenates connections and swath groups; `:28-43` appends swaths and same-group turns; `:46-89` builds cross-group endpoint connections. These calls do not check the resulting PathState seams.
- `types/Path.cpp:98-103` appends state vectors without continuity validation; `:205-222` sums absolute state lengths and appends each swath edge; `types/PathState.cpp:11-13` reconstructs a state endpoint from point, angle, signed direction and len; `objectives/pp_obj/pp_objective.cpp:11-13` returns `path.length()`.
- `types/Path.cpp:346-394,434-440` discretizes turns by spline positions, angles and fixed step length, then reduces states. This is a plausible source of the approximately 25 micrometre PathState endpoint mismatch. It is an inference from source and observed data, not a proven unique cause.

The four checks use 1e-6 m absolute spatial tolerance and 1e-6 m + 1e-10 relative length tolerance, declared before execution. A1 matches generated-to-route polylines as a multiset (including reversal), then matches every route swath edge to ordered final SWATH states. A2 assigns a unique nonwork state range to every adjacent swath pair and checks its endpoints or legal zero-length adjacency. A3 compares every `state.atEnd()` with the following `state.point`. A4 reconciles every absolute state length with PathLength, generated work length and disjoint connector ranges; extra nonwork is separately classified. The independent negative self-test mutated copied observations only: PASS.

## Smoke results and diagnosis

All 6 planned smoke cases returned valid finite paths and matched the original runner. A1, A2 and A4 pass in all 6; A3 passes in 3 and fails in 3. A3 failures are:

| Field | Angle | Maximum gap (m) | Gaps > 1e-6 | Gaps > 1e-5 | Gaps > 1e-4 |
|---|---:|---:|---:|---:|---:|
| HOLD_CONVEX_NO_HOLES_01 | 101 | 2.50010198732e-05 | 1207 | 1206 | 0 |
| HOLD_CONVEX_NO_HOLES_02 | 52 | 2.50011792577e-05 | 40026 | 39998 | 0 |
| HOLD_NONCONVEX_NO_HOLES_02 | 135 | 2.50012261526e-05 | 6852 | 6838 | 0 |

The largest observed gap is 2.50012261526e-05 m. All three failures persist at 1e-5 m and pass at 1e-4 m; this sensitivity does not change the primary verdict. Their length residuals are at most 3.29e-10 m, demonstrating that length agreement alone misses the discontinuities. The recorded first-gap coordinates, state IDs and types are in `s7_failures.jsonl`; all states and route geometry are in `s7_observations.jsonl`. The initial embedded audit fields in that raw JSONL coupled A2/A4 to A3; the corrected independent adjudication is `s7_case_audits.jsonl` and `s7_case_results.csv`.

The predeclared P0 list contains 133 unique field-angle cases: 90 exhaustive 1° oracle angles, 25 differing upstream SwathLength angles and 18 deterministic additional E3/M2 candidate angles. Six were executed and 127 were intentionally left unresolved after the real A3 finding. The 3 passing cases do not establish universal planner semantics. The release repository contains pre-existing dirty tracked files (`M outputs/figures/figure4_runtime_benefit_cost.pdf;  M outputs/figures/figure4_runtime_benefit_cost.png;  M scripts/reproduce_runtime_figure.py`) discovered during this audit; the audit did not edit them. The original source, runner, library and source WKT checks remain unchanged by this audit.
