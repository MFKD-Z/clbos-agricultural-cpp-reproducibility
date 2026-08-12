# Formal orchestration sources

These are release copies of the actual pipeline entry points needed to audit or rerun the main 1° experiment, matched Oksanen adaptation, 42-field MST hierarchy, runtime microbenchmark, and rejected bound candidates.

Release-only portability changes:

- `CLBOS_WORK_ROOT` selects the reconstructed experiment working tree.
- `CLBOS_RUNTIME_ROOT` selects the external clone/build/data cache.
- defaults are repository-local rather than developer-local.

No scientific constants or selection/result logic was changed. These scripts may invoke expensive Route+Path calls. They are never imported or executed by `verify_package.py`.

