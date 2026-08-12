# Reproduction guide

## Level A: analysis only

Requirements: Python 3.10+.

```bash
python scripts/reproduce_numbers.py
python scripts/verify_package.py
```

`reproduce_numbers.py` resolves every input relative to its own package root, so it can run from any current directory. It rewrites only `outputs/tables`. It makes no network request and imports no planner code.

For figures:

```bash
python -m pip install -r environment/python_requirements.txt
python scripts/reproduce_figures.py
```

## Level B: pipeline reconstruction

1. Clone https://github.com/Fields2Cover/Fields2Cover and check out `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426` in detached state.
2. Keep the checkout clean. Do not apply project patches to it.
3. Download Fields2Benchmark record 14524735 using `src/selection/fetch_fields2benchmark.py`.
4. Run `src/selection/prepare_fields.py` to recreate inventory/projection metadata and materialized WKT files.
5. Verify each materialized WKT against `data/provenance/field_inventory.csv` and each frozen selection against its `source_wkt_sha256`.
6. Configure the independent runner with `cmake -S src/runner -B <build-dir> -DF2C_SOURCE_DIR=<Fields2Cover-source>` and build.
7. Set `CLBOS_WORK_ROOT` to a reconstructed work tree containing the original stage directory names and `CLBOS_RUNTIME_ROOT` to the runtime root containing `Fields2Cover-build` and `selected_wkts`.
8. Run only the required orchestration script. Each formal script uses a 900-second per-action timeout and resumable CSV append semantics.

The formal 1° entry point is `src/orchestration/external_competitors_1deg_90.py`. It performs a 180-orientation cheap-bound sweep per held-out field, orders candidates by MST lower bound, and calls the full runner until the certificate stops. `oksanen_matched_1deg_90.py` implements the stated matched discrete adaptation. The 42-field and runtime entries are named directly by their files.

## Planner configuration

- Angular domain: 0–179° in 1° increments for the final held-out evaluation; 0–175° in 5° increments for the 42-field hierarchy.
- Robot width and coverage width: 2 m.
- Body-length protocol binding: 6 m (recorded as protocol metadata; not consumed by the Fields2Cover path planner).
- Minimum turning radius: 2 m.
- Headland: fixed 6 m construction.
- Decomposition: trapezoidal.
- Swath objective: SwathLength.
- Route: Fields2Cover `RoutePlannerBase` shortest route.
- Path: Dubins curves and PathLength.
- Certificate epsilon: 1e-6 m for the main replay/hierarchy.

## Compatibility fallback

The adapter first runs stock trapezoidal decomposition. For the documented split/buffer edge case, it repeats the same geometric split while retaining multiple polygon components produced by the tiny post-split numerical repair. It changes adapter compatibility behavior only; no Fields2Cover source is modified.

## Interpreting results

Deterministic aggregate counts must match exactly. Linear-interpolation percentiles are used for P90/P95. Timing is environment-sensitive and should be checked for table reconstruction and paired-run structure, not exact seconds across hardware.
