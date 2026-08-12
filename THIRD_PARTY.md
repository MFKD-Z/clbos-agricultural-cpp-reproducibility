# Third-party assets

## Fields2Cover

- Project: Fields2Cover
- Official repository: https://github.com/Fields2Cover/Fields2Cover
- Pinned commit: `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`
- Redistributed in this package: **NO**
- Relationship: external dependency
- Upstream license: BSD 3-Clause, as verified in the upstream documentation:
  https://fields2cover.github.io/
- Citation: G. Mier, J. Valente, and S. de Bruin, “Fields2Cover: An Open-Source Coverage Path Planning Library for Unmanned Agricultural Vehicles,” *IEEE Robotics and Automation Letters*, 8(4), 2166–2172, 2023. https://doi.org/10.1109/LRA.2023.3248439

The Fields2Cover repository is not copied into this package. Only project-authored independent adapters are included. Users must clone and build the pinned revision separately and retain its license notices.

## Fields2Benchmark

- Dataset: Fields2Benchmark
- Zenodo record: 14524735 (https://doi.org/10.5281/zenodo.14524735)
- Asset used: `wkt.zip`
- Redistributed WKT files: **NO**
- Public package contains: source identifiers, SHA-256 values, and
  project-generated provenance/selection metadata as applicable
- Record creators: Gonzalo Mier, Ana María Casado Faulí, João Valente, and Sytze de Bruin.

The Zenodo record states that the collection contains 350 agricultural fields
derived from country-specific sources. The record describes different rights
by source: Netherlands material includes public-domain terms, Estonia cites
Creative Commons 3.0 terms, and Lithuania includes copyright and a
non-commercial-use limitation. Because those rights are not uniform, this
package does not redistribute any WKT geometry. Users must consult the
original Zenodo record and its upstream/source-specific license terms before
reuse or redistribution of field geometries.

## Ownership statement

The CLBOS authors do not claim ownership of Fields2Cover, Fields2Benchmark, or their upstream source data. SHA-256 mappings in this package are provenance identifiers, not relicensing statements.

## License scope precedence

`LICENSE.md` defines only the scope of licenses granted by the CLBOS authors.
`THIRD_PARTY.md` defines external ownership and upstream rights. If a
third-party right applies, a project-authored license does not override it.
