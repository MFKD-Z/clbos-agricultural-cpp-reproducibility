# Formal orchestration sources

These are release copies of the core pipeline entry points needed to audit or
rerun the main 1° experiment, matched Oksanen adaptation, 42-field MST
hierarchy, the earlier three-field resolution/runtime continuity study, and
rejected bound candidates.

The final manuscript's primary timing evidence is the v2 stratified 18-field
study archived under `additional_evidence/e3_runtime/`; its numerical
recalculation is handled by `scripts/reproduce_v2_added.py`.

Release-only portability changes in the core orchestration sources:

- `CLBOS_WORK_ROOT` selects the reconstructed experiment working tree.
- `CLBOS_RUNTIME_ROOT` selects the external clone/build/data cache.
- defaults are repository-local rather than developer-local.

No scientific constants or selection/result logic was changed. These scripts
may invoke expensive Route+Path calls. They are never imported or executed by
`scripts/verify_package.py`.
