# CLBOS reproducibility package — v2.0.0

This package supports the manuscript:

> **Certified Lower-Bound Orientation Search under Cross-Stage Objective Mismatch in Agricultural Coverage Path Planning**

Version 2.0.0 extends the previously archived core package with the transfer,
vehicle-sensitivity, secondary mechanism, and stratified repeated-runtime
evidence used by the final manuscript.

Historical v1 DOI: `10.5281/zenodo.21900840`.

The version-specific DOI for v2.0.0 is assigned by Zenodo at publication time
and is therefore not hard-coded inside this GitHub-release payload.

## What is included

### Core evidence retained from v1

- dataset provenance and held-out selection metadata;
- 90-field cross-stage diagnosis;
- fixed Top-K and matched comparator evidence;
- 42-field lower-bound hierarchy and anytime evidence;
- 90-field retrospective tightening / certification-effort evidence;
- rejected-bound and numerical-guard analyses;
- independent Fields2Cover runner/probe source and orchestration code.

### Evidence added in v2

`additional_evidence/e1_transfer/`
: Fixed Top-10 transfer and CLBOS transfer evidence.

`additional_evidence/e2_vehicle_sensitivity/`
: Paired 2.0 m → 2.8 m minimum-turning-radius analysis.

`additional_evidence/e2_secondary_mechanism/`
: 60-field negative mechanism analysis reported in the Supplementary Material.

`additional_evidence/e3_runtime/`
: Stratified 18-field × five-repeat 1° runtime evidence, including the
outcome-independent selection, run-level timing records, field summaries and
system snapshot.

`additional_evidence/provenance_source_snapshots/`
: Path-sanitized source snapshots of the executed E1/E2/E3 scripts. These are
provided for traceability; the portable manuscript-facing recalculation entry
point is `scripts/reproduce_v2_added.py`.

## Fast reproduction: manuscript-facing numbers

Core v1-derived quantities:

```bash
python3 scripts/reproduce_numbers.py
```

v2-added quantities:

```bash
python3 scripts/reproduce_v2_added.py
```

The second command is standard-library only, performs no planner calls and
writes:

- `outputs/tables/v2_added_recomputed.json`
- `outputs/tables/v2_added_recomputed.csv`

The recomputed v2 results include:
- Top-10/CLBOS transfer exactness and evaluation totals;
- the paired turning-radius effort change and weak paired gap-effort association;
- the negative 60-field field-difficulty correlations/model summaries;
- the 18-field repeated-runtime speedup, reduction, bound-acquisition fraction
  and favourable Top-10 timing ratio.

## Figures

Install the documented Python plotting dependencies:

```bash
python3 -m pip install -r environment/python_requirements.txt
```

Then run:

```bash
python3 scripts/reproduce_figures.py
python3 scripts/reproduce_runtime_figure.py
```

These rebuild manuscript Figs. 2–3, Supplementary Fig. S1, and a data-level
reproduction of the final runtime Fig. 4.

Fig. 1 is conceptual and is not data-generated.

## Full planner reconstruction

See `docs/REPRODUCTION_GUIDE.md`.

Fields2Cover and Fields2Benchmark are external resources and are not
redistributed. The exact Fields2Cover revision and Fields2Benchmark record are
documented in `THIRD_PARTY.md` and the reproduction guide.

## Interpretation boundaries

1. Fixed Top-10 remained exact in every tested transfer domain; no fixed-K
   transfer failure is claimed.
2. CLBOS is not claimed to be uniformly cheaper than a successful fixed budget.
3. The turning-radius intervention supports an aggregate directional
   sensitivity result, not a universal field-level mechanism.
4. The 60-field secondary analysis does not support a simple P90
   relaxation-gap explanation of field-level certification effort.
5. The favourable Top-10 runtime omits ranking acquisition and is not an
   equal-scope speed comparison.
6. The 18-field timing subset represents the three held-out benchmark geometry
   strata, not agricultural deployment populations.
7. The certificate is mathematical over the stated finite orientation set and
   exact-arithmetic admissibility model; formal IEEE-754 verification is not
   claimed.

## Integrity and licensing

- `MANIFEST.sha256` is the authoritative package hash manifest.
- `LICENSE_SCOPE_MAP.csv` covers every distributed file.
- Project-authored software: BSD-3-Clause.
- Project-authored documentation and eligible derived research materials:
  CC BY 4.0.
- Third-party-derived selection/provenance records remain subject to upstream
  rights as documented in `THIRD_PARTY.md`.
