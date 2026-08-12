# CLBOS reproducibility package

**Manuscript:** *Cross-Stage Objective Mismatch and Certified Elimination of Downstream Evaluations in Agricultural Coverage Path Planning*  
**Target journal:** *Biosystems Engineering*

This repository is the minimal public evidence and code package for independently checking the manuscript's data provenance, discrete-domain results, certified evaluation counts, and data-driven tables and figures. It contains no new experiment and no replacement scientific authority.

## 1. What this repository reproduces

Level A recomputes the reported 90-field cross-stage diagnosis, tie-aware result, matched comparators, Top-K exactness, the unique Top-5 miss, the 42-field MST hierarchy and anytime summaries, the 90-field post-hoc replay, hard-tail and family totals, the three-field repeated runtime table, and Appendix sensitivity/negative-candidate summaries from packaged row-level CSV evidence.

Level B preserves the independent Fields2Cover runner/adapters and the orchestration entry points required to reconstruct the planner pipeline after separately obtaining the public dataset and pinned third-party source.

## 2. What it does not claim or reproduce

This package does not claim continuous-angle optimality, floating-point formal verification, universal computational superiority, causal effects of geometry family, a faithful reproduction of Oksanen's original implementation, or a preregistered 90-field replay. The Oksanen result is a matched discrete adaptation. Runtime evidence is a three-field microbenchmark with five repeats per method and resolution; it is not population-level runtime evidence.

The package does not redistribute Fields2Cover, Fields2Benchmark WKT files, manuscript drafts, project history, internal governance material, or failed development routes.

## 3. Repository structure

- `data/provenance`: source inventory and exclusion record.
- `data/development` and `data/heldout`: frozen selection manifests; WKT paths are portable placeholders, not bundled data.
- `data/derived`: row-level evidence used by Level A.
- `src/runner`: independent C++ runner and bound probes.
- `src/orchestration`: pipeline scripts actually used, with release-only path configuration changes.
- `src/selection`: acquisition, preprocessing, and held-out selection code.
- `scripts`: analysis, figure, and package verification entry points.
- `outputs`: regenerated tables and figures.
- `docs`: claim-to-evidence map and detailed reproduction guide.

## 4. Public source dataset

Fields2Benchmark is Zenodo record [14524735](https://doi.org/10.5281/zenodo.14524735). The record describes 350 agricultural fields and supplies `wkt.zip`. This package publishes the 349-row usable inventory, the single preprocessing exclusion, source-relative paths, and source WKT SHA-256 values; it does not republish the WKT archive.

## 5. Exact Fields2Cover revision

- Repository: [Fields2Cover/Fields2Cover](https://github.com/Fields2Cover/Fields2Cover)
- Commit: `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`
- Project code is an independent adapter and does not modify the checked-out Fields2Cover algorithm source.

## 6. Environment

Level A requires Python 3.10 or newer and only the standard library. Figure regeneration additionally requires Matplotlib. Level B requires Linux, CMake, a C++17 toolchain, Fields2Cover's build dependencies, Shapely, and pyproj. See `environment/README.md`, `environment/python_requirements.txt`, and `environment/system_snapshot.txt`.

## 7. Quick start: analysis only

From the package root:

```bash
python scripts/reproduce_numbers.py
python scripts/verify_package.py
```

The first command writes `outputs/tables/recomputed_summary.json` and compact CSV tables. The second checks the expected manuscript anchors, local-path sanitation, secrets, cache/build debris, and the manifest when present. It never invokes a planner.

## 8. Full pipeline setup

Follow `docs/REPRODUCTION_GUIDE.md`. Obtain Fields2Benchmark from Zenodo and Fields2Cover at the pinned commit, build the independent runners, materialize selected WKT files from their source paths and SHA-256 mappings, then invoke only the desired orchestration stage. Formal runs are intentionally not launched by the package verifier.

## 9. Reproduce manuscript tables

Run `python scripts/reproduce_numbers.py`. Generated tables cover provenance/selection, cross-stage diagnosis, Top-K, 42-field MST, anytime certificates, 90-field replay, runtime, and Appendix summaries. Every result is aggregated from packaged row-level evidence; manuscript numbers are used only as verification expectations in `verify_package.py`.

## 10. Reproduce manuscript data figures

Install the optional analysis dependency and run:

```bash
python -m pip install -r environment/python_requirements.txt
python scripts/reproduce_figures.py
```

The script rebuilds all three data-driven manuscript figures as PNG and PDF:

- Fig. 2: the unique Top-5 failure diagnostic;
- Fig. 3: anytime certification; and
- Fig. 4: the CLBOS-MST Full-evaluation empirical CDF.

Fig. 1 is a conceptual schematic and is therefore not generated from packaged data.

## 11. Expected key checks

The verifier checks: 350 source WKT files, 349 usable fields, one exclusion; a 90-field 30/30/30 held-out set; 65 aligned and 25 disjoint cross-stage fields; Top-K exact counts of 65/80/85/89/90; 259 to 180 Full calls on 42 fields; and 2057 to 1428 Full calls on the 90-field replay, including its hard tail and family totals.

## 12. Runtime scope

Runtime results are descriptive measurements for three fixed held-out fields, four angular resolutions, two methods, and five paired-order repeats. Timing values depend on the recorded system. They support a microbenchmark table only.

## 13. Numerical-certification scope

Admissibility of the MST-strengthened lower bound is established analytically under assumptions A1–A4 and the exact-arithmetic model stated in the manuscript. The floating-point implementation is additionally checked empirically against the packaged exhaustive finite-domain oracle. Those empirical CSV checks recover the finite-domain implementation results; they do not establish the mathematical admissibility claim. The certificates are not continuous-angle certificates and are not proofs about arbitrary floating-point implementations.

## 14. Post-hoc analyses disclosure

The 90-field incremental lower-bound replay and epsilon sensitivity are post-hoc analyses of frozen evidence. Epsilon sensitivity is Lsw-only replay. DirectDist, degree relaxation, and kinematic/Dubins-MST are negative or rejected candidate evidence and are not presented as components of the final CLBOS-MST method.

## 15. Data provenance

`REPRO_EVIDENCE_MAP.csv` and `docs/CLAIM_EVIDENCE_MAP.md` connect each public claim to a source authority, its original SHA-256, its packaged path, and the recomputation performed. `MANIFEST.sha256` covers every public file except the manifest itself.

## 16. Third-party dependencies

See `THIRD_PARTY.md`. Fields2Cover is BSD-3-Clause. Fields2Benchmark contains country-source-specific rights, including a non-commercial limitation described for the Lithuanian source data; users must consult the Zenodo record and its bundled license before redistributing field geometry.

## 17. Citation

Use `CITATION.cff` for the author-approved citation metadata. ORCIDs, a repository URL, and DOI fields are intentionally omitted because they have not been supplied.

## 18. Contact

Corresponding author: Miao Yu, School of Mechanical Engineering, Sichuan University, Chengdu, China; `miaoyu@scu.edu.cn`.

## 19. License

- Project-authored software: [BSD-3-Clause](LICENSES/BSD-3-Clause.txt).
- Project-authored documentation and eligible original research materials:
  [CC BY 4.0](LICENSES/CC-BY-4.0.txt).
- Third-party and rights-sensitive materials: upstream terms apply; see
  [THIRD_PARTY.md](THIRD_PARTY.md).

The precise file-level boundaries are defined in [LICENSE.md](LICENSE.md) and
`LICENSE_SCOPE_MAP.csv`. The mixed-license `CITATION.cff` intentionally omits
a single top-level license field; that omission does not imply that
BSD-3-Clause governs non-software materials.
