# Dataset acquisition and selection

`fetch_fields2benchmark.py` retrieves Zenodo metadata and the WKT-containing archive. `prepare_fields.py` validates, projects, classifies, hashes, and inventories fields. `freeze_heldout_selection.py` applies the deterministic, outcome-blind, family-balanced area-rank rule after excluding all frozen development selections.

The public CSV manifests use `selected_wkts/<sha256>.wkt` as a portable materialization path. The WKT files themselves are not distributed.

