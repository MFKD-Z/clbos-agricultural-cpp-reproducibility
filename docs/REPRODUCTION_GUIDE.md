# Reproduction guide

## Level A: manuscript-facing numerical reproduction

Requirements: Python 3.10+.

Core evidence:

```bash
python3 scripts/reproduce_numbers.py
```

v2-added evidence:

```bash
python3 scripts/reproduce_v2_added.py
```

Both scripts resolve inputs relative to the package root. They make no network
requests and perform no Fields2Cover calls.

For figures:

```bash
python3 -m pip install -r environment/python_requirements.txt
python3 scripts/reproduce_figures.py
python3 scripts/reproduce_runtime_figure.py
```

`reproduce_figures.py` rebuilds manuscript Figs. 2–3 and Supplementary Fig. S1.
`reproduce_runtime_figure.py` rebuilds a data-level representation of final
Fig. 4 from the packaged 18-field runtime records.

## Level B: planner reconstruction

1. Clone `https://github.com/Fields2Cover/Fields2Cover`.
2. Check out revision `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`.
3. Keep the upstream checkout clean; do not modify Fields2Cover source.
4. Obtain Fields2Benchmark Zenodo record `14524735`.
5. Use `src/selection/fetch_fields2benchmark.py` and
   `src/selection/prepare_fields.py` to reconstruct the field inventory and
   local projected geometries.
6. Verify reconstructed geometries against the packaged SHA-256 provenance.
7. Configure the independent runner:

```bash
cmake -S src/runner -B <build-dir> -DF2C_SOURCE_DIR=<Fields2Cover-source>
cmake --build <build-dir>
```

8. Use the core orchestration sources under `src/orchestration/` for the
   original held-out/hierarchy experiments.
9. The exact executed E1/E2/E3 source snapshots are retained under
   `additional_evidence/provenance_source_snapshots/`. Because those snapshots
   were originally run in a project workspace, absolute local paths have been
   sanitized in this public copy. Their scientific constants and algorithms are
   retained for audit; the portable Level-A scripts above are the supported
   manuscript-facing reproduction path for the added evidence.

## Planner configuration

- Primary angular domain: 0–179° in 1° increments.
- Development hierarchy: 0–175° in 5° increments.
- Resolution-transfer domain: 0.5° increments where stated.
- Coverage width: 2 m.
- Robot width: 2 m.
- Baseline minimum turning radius: 2 m.
- Controlled transfer minimum turning radius: 2.8 m.
- Headland: 6 m.
- Decomposition: trapezoidal.
- Swath objective: SwathLength.
- Route: Fields2Cover `RoutePlannerBase::genRoute`.
- Path: Fields2Cover `PathPlanning::planPath` with Dubins curves.
- Complete objective: Fields2Cover PathLength.
- Per-planner-call timeout: 900 s; timeout is an unresolved execution failure,
  not model infeasibility.

## Runtime interpretation

The primary runtime evidence uses 18 benchmark-stratified fields, five repeats,
serial execution and counterbalanced method order. Exhaustive and CLBOS timings
are end-to-end at the Python-driver level. The fixed Top-10 reference times only
ten downstream complete evaluations using a precomputed ranking and therefore
is deliberately favourable and non-equal-scope.

Absolute wall times are hardware dependent; the archived values are the
authority for the manuscript's reported timing study.
