# License scope

This file explains which license applies to each part of the CLBOS
reproducibility package. It is a scope statement, not a third license.
`LICENSE_SCOPE_MAP.csv` is the file-level inventory. If a file or directory
contains a more specific notice, that notice controls.

Unless a file or directory states otherwise:

- project-authored software is licensed under the BSD 3-Clause License
  (`BSD-3-Clause`);
- project-authored documentation and eligible original research materials are
  licensed under the Creative Commons Attribution 4.0 International Public
  License (`CC-BY-4.0`).

Third-party materials are excluded from these grants and remain subject to
their original terms. No repository-wide statement overrides third-party
rights.

## Project-authored software — BSD-3-Clause

The BSD-3-Clause grant covers the project-authored software and software
support files identified as `BSD-3-Clause` in `LICENSE_SCOPE_MAP.csv`. This
includes executable/source files under `src/` (but not its README files),
software under `scripts/`, `.gitignore`, and
`environment/python_requirements.txt`.

The license text is in `LICENSES/BSD-3-Clause.txt`. The code calls public
Fields2Cover interfaces but does not copy or modify the Fields2Cover source.
Fields2Cover remains under its own upstream license.

## Project-authored content — CC-BY-4.0

The CC-BY-4.0 grant covers only the files identified as `CC-BY-4.0` in
`LICENSE_SCOPE_MAP.csv`, including:

- project-authored documentation and explanatory material;
- project-generated numerical results under `data/derived/`;
- project-generated tables under `outputs/tables/`;
- project-generated figures under `outputs/figures/`; and
- project-authored citation, audit, provenance, manifest, and scope metadata.

The license notice is in `LICENSES/CC-BY-4.0.txt`. References to external
projects, field identifiers, and source hashes are factual provenance
references; they do not license the referenced external material.

## Fields2Benchmark and rights-sensitive metadata

Fields2Benchmark source WKT and satellite images are not redistributed in
this package. Files under `data/provenance/`, `data/development/`, and
`data/heldout/` contain a mixture of project-generated selection/provenance
metadata and Fields2Benchmark source identifiers, paths, hashes, country
codes, and geometry-derived attributes. To avoid implying authority over the
external source material, these eight files are excluded as whole files from
the authors' BSD-3-Clause and CC-BY-4.0 grants. Upstream and source-specific
rights continue to apply. Consult `THIRD_PARTY.md` and Zenodo record 14524735
before reuse or redistribution.

This package does not grant rights in any referenced Fields2Benchmark field
geometry. A hash or identifier is a provenance key, not a copy of the geometry
and not a relicensing statement.

## Third-party materials and license texts

The CLBOS authors do not relicense Fields2Cover, Fields2Benchmark, third-party
WKT, upstream datasets, third-party names or marks, or the standardized legal
texts stored under `LICENSES/`. Those materials and references are governed by
their upstream terms. `THIRD_PARTY.md` records the applicable ownership and
redistribution boundaries.

`LICENSE.md` defines only the scope of licenses granted by the CLBOS authors.
`THIRD_PARTY.md` defines external ownership and upstream rights. If a
third-party right applies, the project-authored license does not override it.

## Mixed-license citation metadata

`CITATION.cff` intentionally omits a single top-level `license` field because
this is a mixed-license repository. That omission does not change the scoped
BSD-3-Clause software grant or the scoped CC-BY-4.0 content grant described
here.
