# Reproducibility scope — v2.0.0

## Scientific status

- `SCIENTIFIC_METHOD=FROZEN`
- `NEW_EXPERIMENT_COUNT=0`
- `NEW_PLANNER_CALLS_DURING_V2_PACKAGING=0`
- `SCIENTIFIC_RESULT_CHANGED=false`

Version 2.0.0 is a packaging and evidence-completion release. It does not
introduce a new method or a new scientific experiment.

## Level A — analysis-only reproduction

The following commands use packaged evidence and do not call Fields2Cover:

```bash
python3 scripts/reproduce_numbers.py
python3 scripts/reproduce_v2_added.py
```

They recalculate the manuscript-facing core and v2-added numerical results.

## Level B — planner reconstruction

The package retains the project-authored runner/probe and core orchestration
source required to reconstruct the original planner experiments. E1/E2/E3
executed-script snapshots are retained under
`additional_evidence/provenance_source_snapshots/` for traceability. They are
path-sanitized snapshots, not portable one-command entry points.

The external Fields2Cover and Fields2Benchmark resources are not redistributed.

## Scope boundaries

- Optimality is over the stated finite angular candidate domains.
- Mathematical admissibility is under assumptions A1–A4 and exact arithmetic.
- Floating-point implementation recovery is checked empirically against the
  exhaustive finite-domain reference.
- Fixed Top-10 remained exact in all tested transfer domains.
- The paired turning-radius analysis supports aggregate sensitivity only.
- The 60-field secondary analysis does not identify a simple global
  relaxation-gap explanation of certification difficulty.
- The primary runtime evidence is the stratified 18-field × five-repeat study.
- The favourable Top-10 runtime is downstream-only and deliberately
  non-equal-scope.
- The runtime subset is benchmark-stratified and is not a sample of deployment
  populations.
