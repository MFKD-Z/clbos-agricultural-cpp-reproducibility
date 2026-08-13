# E3 Protocol Freeze — Representative Runtime

- `TASK=CLBOS_E3_REPRESENTATIVE_RUNTIME`
- `FORMAL_RUN=true`
- `FIELD_COUNT=18`
- `REPEATS=5`
- `RESOLUTION=1deg`
- `CANDIDATE_COUNT=180`
- `FROZEN_K=10`
- `FIELDS2COVER_HEAD=92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`
- `SCRIPT_SHA256=837327121dedbd385e2cf53657afcc4dacce50113816c6b305e12436f6f05e6c`

## Selection

Formal E3 selects 18 fields from the existing 90-field held-out metadata:
six per geometry family after excluding the nine fields previously used in
resolution-scaling timing. Within each family, fields are sorted by
`(area_m2, field_id)` and six equal-rank-bin midpoints are chosen.

No runtime, CLBOS Nfull, oracle rank, Top-K outcome, or downstream objective
enters the selection rule.

## Timing methods

1. `EXHAUSTIVE`: full planner over all 180 orientations.
2. `CLBOS_MST`: full 180-orientation MST bound sweep followed by certified
   selected Full calls; end-to-end Python driver wall time including subprocess overhead.
3. `TOP10_LSW_PRECOMPUTED`: frozen top ten orientations under the authoritative
   precomputed 1-degree SwathLength ranking; timing includes only downstream Full calls.

The third timing deliberately favors Top-10. Therefore CLBOS-vs-Top10 is a
conservative upper-bound estimate of the certificate premium, NOT an equal-scope
end-to-end runtime comparison.

## Runtime controls

- one MST + one Full warm-up per field;
- serial execution;
- deterministic counterbalanced method order across fields/repeats;
- timeout = 900 s per subprocess call;
- five repeats in the formal run;
- successful run keys are resumable and never silently overwritten;
- no method or parameter tuning after outcomes.
