# S7 pinned-planner runtime audit: coordinate-free evidence archive

This folder archives the **existing** October 11–12, 2026 S7 runtime audit of the CLBOS adapter and Fields2Cover pinned at commit `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`. The public files are publication copies of the genuine local records. No planner case was rerun to make this package. The production adapter, original executable and linked library SHA-256 values were respectively `348a227182252feb63743fb9cd711fec6dd0a57ce7891b99dda3db4d1ab23658`, `4c89a57f2ffe4d1bd00f42e7743936297217cb2e91971062eaf61f3046712f4c` and `1338ade681056f031806bb1349f3a5cd5392e614a00c5fac3170ec7f3574ceda`. Their original identities were checked locally before archival; the binary and library are not redistributed here.

## What was observed

`s7_predeclared_cases.json` contains 133 unique field-orientation keys. Six smoke cases actually ran and returned finite paths. The remaining **127 were not executed** after the genuine strict A3 failure; their status is `UNRESOLVED_NOT_RUN_AFTER_A3_FAILURE`, not PASS or model infeasible. The original S7 gate remains **FAIL**: 3 of 6 executed cases fail the declared `PathState::atEnd()` to next stored point continuity test at 1e-6 m, with 48,085 strict `TURN→TURN` gaps across those cases.

The later, read-only sampled-polyline interpretation passes for **44/44 observed required inter-swath connectors**. All 57,132 observed nonworking states are assigned to those connector ranges. This does not reverse the strict A3 result. The implementation-wide statuses of A1, A2 and A4 remain **INCONCLUSIVE**; the mathematical Proposition 1 remains **conditional** on its stated swath, connector and charging predicates. The refined implementation gate is INCONCLUSIVE. These six observations are not program-wide certification.

## Files and verification

The publication copies retain the original audit names: `S7_PINNED_PLANNER_AUDIT.md`, `s7_predeclared_cases.json`, `s7_observations.jsonl`, `s7_failures.jsonl`, `s7_case_audits.jsonl`, and `s7_case_results.csv`. The later analysis is in `s7_polyline_closure/`, including its report, connector-level `s7_polyline_case_checks.csv`, source call chain, branch coverage, proof obligation matrix and unresolved obligations. The source snapshots `s7_observer.cpp`, `s7_audit.py`, `finalize.py`, and `s7_polyline_closure/build_closure.py` show the code used for observation, independent negative self-test and sampled-polyline reanalysis. The original `negative_selftest.json` is included. Source snapshots have local path prefixes replaced with placeholders; they are provenance records, not ready-to-run cross-machine scripts. The observer binary, third-party WKT, geometry-rich A3 gap table and local build artifacts are not included.

Run this standard-library-only, read-only check from any directory:

```sh
python additional_evidence/s7_planner_semantics/verify_archive.py
```

It checks published file SHA-256 values; cross-checks original hashes recorded by the two original manifests; verifies 133/6/127, 3/6 strict A3 failures, 48,085 gaps, 44/44 sampled-polyline connector rows and 57,132 assigned nonworking states; and checks coordinate fields were removed from the JSON evidence. To recreate the publication transform **only when the original local audit exists**, run:

```sh
python additional_evidence/s7_planner_semantics/prepare_publication.py \
  --source /path/to/original/s7_pinned_planner_semantics_audit \
  --local-manifest /path/outside/public/repository/s7_archive_local_manifest.json
```

`publication_manifest.json` lists each original file's size, timestamp and SHA-256, the SHA-256 of each public copy, and the exact redaction categories. The original run's `s7_evidence_manifest.json` and later `s7_polyline_closure/s7_polyline_evidence_manifest.json` are included as path-sanitized copies. Their original SHA-256 values are recorded in `publication_manifest.json`. The restricted local manifest retains absolute original paths, timestamps and full-trace hashes outside the public repository. The complete original observation trace remains unchanged locally.

The directory's `.gitattributes` disables checkout newline conversion so these hashes verify on Windows clones as well as on other platforms.

## Public reproducibility limit and rights

The original JSONL trace contained metric coordinates of generated swaths, route connections, state points and reconstructed endpoints. Releasing those sequences could effectively redistribute Fields2Benchmark-derived field geometry, whose source rights vary; see the repository's `THIRD_PARTY.md` and `LICENSE_SCOPE_MAP.csv`. Publication copies remove `point`, `end`, `points`, `expected`, `observed`, `start_expected`, `end_expected` and state `angle` fields, replace route-connection coordinate sequences with point counts, and replace local file paths. Original field identifiers and hashes remain as provenance references. No WKT polygon or coordinate sequence is published.

The public package independently verifies the **recorded numerical counts and status consistency**, but it cannot recompute geometric endpoint distances or the 44 connector judgments from spatial coordinates. A researcher with appropriate access to the original geometry-rich trace can use its hashes in `publication_manifest.json` and the restricted local manifest to authenticate that fuller record. The public `s7_polyline_case_checks.csv` reports the connector-level numerical adjudications, not a substitute for the redacted coordinates.

The unresolved implementation obligations include one-to-one generated-to-route swath identity, nonempty charged connection construction, possible endpoint correction after turn charge calculation, and handling of empty or nonfinite paths. They are detailed in `s7_polyline_closure/s7_proof_obligation_matrix.csv` and `s7_polyline_closure/s7_unresolved_obligations.md`.

Zenodo v2.2.0 (`10.5281/zenodo.23295025`) **does not contain this newer S7 audit package**. This evidence-only Git branch does not modify that Zenodo archive, an existing GitHub release, the planner, or the frozen experiment outputs.
