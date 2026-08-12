# Publication handoff

The reproducibility package is technically ready and the author-owned license
decision has been closed with file-level scope boundaries.

## Current readiness

- `FINAL_STATUS=GITHUB_PUBLICATION_READY`
- `TECHNICAL_PACKAGE_READY=true`
- `CITATION_METADATA=PASS`
- `PREMATURE_PUBLICATION_METADATA=NONE`
- `LICENSE_STATUS=PASS`
- `SOFTWARE_LICENSE=BSD-3-Clause`
- `DOCUMENTATION_LICENSE=CC-BY-4.0`
- `THIRD_PARTY_RIGHTS_BOUNDARY=PASS`
- `ANALYSIS_REPRODUCTION_STATUS=PASS`
- `FRESH_COPY_STATUS=PASS`
- `PRIVATE_PATH_SCAN=PASS`
- `SECRET_SCAN=PASS`
- `MANIFEST_VERIFICATION=PASS`
- `NEW_EXPERIMENT_COUNT=0`
- `NEW_PLANNER_CALL_COUNT=0`
- `SCIENTIFIC_RESULT_CHANGED=false`
- `GITHUB_READY=true`
- `PUBLIC_RELEASE_PACKAGE_READY=true`
- `ZENODO_READY=false`
- `LOCAL_PUBLIC_PACKAGE_FINALIZED=true`
- `NEXT_ACTION=CREATE_CLEAN_GITHUB_REPOSITORY`

`GITHUB_READY=true` means the package is ready to place in a new clean public
repository; it is not publication authorization. `ZENODO_READY=false` remains
normal until a GitHub release exists. Citation metadata is complete for this
round; ORCIDs, a repository URL, and DOI fields are omitted because none were
supplied.

## Publication sequence

1. Run final package verification.
2. Create a clean public GitHub repository.
3. Upload only this release package.
4. Verify rendered Markdown, license display, and citation metadata.
5. Tag `v1.0.0`.
6. Connect GitHub to Zenodo.
7. Archive the release.
8. Obtain the DOI.
9. Update the manuscript Data Availability statement.
10. Submit the manuscript.

This handoff does not authorize creating a repository, pushing, publishing a
release, creating a Zenodo deposit, or obtaining a DOI. Those steps require a
separate explicit user authorization.

The package does not redistribute Fields2Cover source or Fields2Benchmark WKT. `THIRD_PARTY.md` remains the authority for third-party attribution and redistribution boundaries.
