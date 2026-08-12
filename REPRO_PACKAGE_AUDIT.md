# Reproducibility package audit

## Release-closure status

- `FINAL_STATUS=GITHUB_PUBLICATION_READY`
- `TECHNICAL_PACKAGE_READY=true`
- `PACKAGE_ROOT=.`
- `PACKAGE_SIZE_BYTES=000004892419`
- `PUBLIC_FILE_COUNT=000085`
- `SCIENTIFIC_PARAMETER_CONSISTENCY=PASS`
- `CERTIFICATION_SEMANTICS=PASS`
- `FIGURE_REPRO_DESCRIPTION=PASS`
- `CITATION_METADATA=PASS`
- `PREMATURE_PUBLICATION_METADATA=NONE`
- `ANALYSIS_REPRODUCTION=PASS`
- `FRESH_COPY_ANALYSIS_REPRODUCTION=PASS`
- `PRIVATE_PATH_SCAN=PASS`
- `SECRET_SCAN=PASS`
- `NEW_EXPERIMENT_COUNT=0`
- `NEW_PLANNER_CALL_COUNT=0`
- `SCIENTIFIC_RESULT_CHANGED=false`
- `LICENSE_STATUS=PASS`
- `SOFTWARE_LICENSE=BSD-3-Clause`
- `DOCUMENTATION_LICENSE=CC-BY-4.0`
- `THIRD_PARTY_BOUNDARY=PASS`
- `LICENSE_CONFLICT_SCAN=PASS`
- `GITHUB_READY=true`
- `PUBLIC_RELEASE_PACKAGE_READY=true`
- `ZENODO_DEPOSIT_READY=false`
- `ZENODO_PUBLISHED=false`
- `ZENODO_READY=false`
- `LOCAL_PUBLIC_PACKAGE_FINALIZED=true`

The technical and mixed-license package is ready for placement in a new clean
public GitHub repository. `ZENODO_READY=false` is expected until a GitHub
release and Zenodo record actually exist. No publishing action was performed
or authorized during this closure.

## R1.3 pre-GitHub metadata cleanup

- `STAGE_1_SUPERSEDED_LICENSE_FILE_REMOVAL=PASS`
- `STAGE_2_CITATION_PREPUBLICATION_HYGIENE=PASS`
- `STAGE_3_PUBLICATION_METADATA_CONSISTENCY=PASS`
- `STAGE_4_ANALYSIS_REPRODUCTION=PASS`
- `STAGE_5_FRESH_COPY=PASS`
- `STAGE_6_PUBLIC_SANITIZATION=PASS`
- `STAGE_7_MANIFEST_REGENERATION=PASS`
- `LICENSE_DECISION_REQUIRED_FILE_COUNT=0`
- `STALE_LICENSE_DECISION_REFERENCE_COUNT=0`
- `PREMATURE_JOURNAL_METADATA_COUNT=0`
- `PREMATURE_ARTICLE_DOI_COUNT=0`
- `PREMATURE_PUBLICATION_CLAIM_COUNT=0`
- `CITATION_AUTHOR_ORDER_MATCH=true`
- `SCIENTIFIC_VALUE_CHANGE_COUNT=0`
- `MANIFEST_HASHED_FILE_COUNT=84`

The CFF describes the reproducibility package and does not claim that the
pre-submission manuscript has been accepted or published. The only journal
statement retained in public prose identifies Biosystems Engineering as the
target journal.

## R1.1 six-stage closure

### Stage 1: planner-parameter documentation

- `STAGE_1_PARAMETER_CONSISTENCY=PASS`
- `MIN_TURN_RADIUS_PUBLIC_VALUE=2.0_m`
- `PARAMETER_CONFLICT_COUNT=0`

The public guide and runner README now match the frozen runner authority: 2 m coverage width, 2 m robot width, 2 m minimum turning radius, 6 m total headland width, and a nominal 6 m body-length protocol binding that the Fields2Cover path planner does not consume. Contextual review retained legitimate 3 m values describing each half of the 6 m headland construction.

### Stage 2: certification semantics

- `STAGE_2_CERTIFICATION_SEMANTICS=PASS`
- `EMPIRICAL_PROOF_OF_ADMISSIBILITY_LANGUAGE_COUNT=0`

MST-bound admissibility is mapped to the analytical proposition/theorem under assumptions A1–A4 and exact arithmetic in the associated manuscript. Packaged exhaustive CSV evidence is mapped only to floating-point implementation recovery on the finite oracle domain; it is not described as proving mathematical admissibility.

### Stage 3: figure reproduction truthfulness

- `STAGE_3_FIGURE_REPRO_TRUTHFULNESS=PASS`
- `MANUSCRIPT_DATA_FIGURES_REPRODUCIBLE=Fig.2,Fig.3,Fig.4`
- `NONREPRODUCIBLE_FIGURES=none`

`scripts/reproduce_figures.py` rebuilds Fig. 2 (unique Top-5 failure diagnostic), Fig. 3 (anytime certification), and Fig. 4 (CLBOS-MST Full-evaluation empirical CDF) from packaged CSV evidence. Fig. 1 is a conceptual schematic and is outside data-script reproduction. This is derived visual reproduction, not a new experiment.

### Stage 4: citation metadata

- `STAGE_4_CITATION_METADATA=PASS`
- `CITATION_AUTHOR_COUNT=5`
- `CITATION_AUTHOR_ORDER_MATCH=true`

`CITATION.cff` contains the author-supplied title, ordered author list, common affiliation, and Miao Yu's corresponding-author email. No ORCID, DOI, or repository URL was invented. The obsolete template was removed.

### Stage 5: license boundary

- `STAGE_1_LICENSE_BOUNDARY_AUDIT=PASS`
- `UNRESOLVED_LICENSE_SCOPE_COUNT=0`
- `THIRD_PARTY_ASSET_REDISTRIBUTION_COUNT=0`
- `STAGE_2_BSD3_LICENSE=PASS`
- `BSD3_SCOPED_FILE_COUNT=24`
- `STAGE_3_CC_BY_4_LICENSE=PASS`
- `CC_BY_4_SCOPED_FILE_COUNT=51`
- `UPSTREAM_RIGHTS_SCOPED_FILE_COUNT=10`
- `STAGE_4_LICENSE_SCOPE_DOCUMENT=PASS`
- `STAGE_5_THIRD_PARTY_BOUNDARY=PASS`
- `THIRD_PARTY_RELICENSE_CONFLICT_COUNT=0`
- `STAGE_6_README_LICENSE_INTEGRATION=PASS`
- `STAGE_7_CITATION_LICENSE_METADATA=PASS`
- `STAGE_8_PUBLICATION_HANDOFF=PASS`
- `LICENSE_STATUS=PASS`

`LICENSE_SCOPE_MAP.csv` inventories every public file. Project-authored
software is BSD-3-Clause; project-authored documentation and eligible original
research materials are CC-BY-4.0. Eight mixed Fields2Benchmark
provenance/selection files and two standardized license notice/text files are
explicitly subject to upstream rights rather than author relicensing. The
package redistributes neither Fields2Cover source nor Fields2Benchmark WKT.
The superseded pre-decision license notice has been removed from the public
package. `LICENSE.md`, `LICENSE_SCOPE_MAP.csv`, and this audit contain only the
current author-approved license state.

### Stage 6: package verification

- `ANALYSIS_REPRODUCTION_STATUS=PASS`
- `FRESH_COPY_STATUS=PASS`
- `PROJECT_ROOT_DEPENDENCY_COUNT=0`
- `HIDDEN_SOURCE_DEPENDENCY_COUNT=0`
- `PRIVATE_PATH_COUNT=0`
- `SECRET_SCAN_RESULT=PASS`
- `CACHE_SCAN=PASS`
- `BUILD_ARTIFACT_SCAN=PASS`
- `BACKUP_SCAN=PASS`
- `LICENSE_CONFLICT_SCAN=PASS`
- `MANIFEST_VERIFICATION=PASS`

The analysis-only reproduction and package verifier pass in the package and in an isolated fresh copy. The manifest covers every public file except itself, avoiding an impossible self-referential hash.

## Frozen scientific anchors

- Provenance: 350 source WKT records, 349 usable fields, one exclusion.
- Held-out set: 90 fields, 65 aligned and 25 disjoint.
- Top-K exact recovery: 65, 80, 85, 89, 90.
- 42-field empirical replay: 259 to 180 complete evaluations.
- 90-field replay: 2057 to 1428, saving 629 (30.58%).
- CLBOS-MST hard-tail anchors: mean 15.867, P50 4.5, P90 35, P95 71.35, maximum 163.
- Family Full-evaluation totals: 949, 250, 229.

These values are reproduced from unchanged frozen evidence. No new experiment or Fields2Cover Route/Path planner call was made during release closure.

## Scope guardrails

The package does not claim continuous-angle optimality, floating-point formal verification, universal computational superiority, causal geometry-family effects, a faithful reproduction of Oksanen's original implementation, or preregistration of the 90-field replay. Runtime evidence remains a three-field, five-repeat descriptive microbenchmark. DirectDist, degree relaxation, and kinematic/Dubins-MST remain negative or rejected candidates.

## Release state and next action

- `SCIENTIFIC_CONTENT=FROZEN`
- `REPRODUCIBILITY_PACKAGE=FROZEN`
- `NEW_EXPERIMENT_COUNT=0`
- `NEW_PLANNER_CALL_COUNT=0`
- `SCIENTIFIC_RESULT_CHANGED=false`
- `NEXT_ACTION=CREATE_CLEAN_GITHUB_REPOSITORY`

Creating or publishing that repository and creating a Zenodo deposit require
separate explicit user authorization.
