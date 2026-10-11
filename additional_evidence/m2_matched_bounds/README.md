# CLBOS M2 matched-bounds evidence

This directory is an additional, run-level reproducibility deposit for the
matched lower-bound ablation. It does not replace the original CLBOS archive
or rerun the planner.

## Protocol and scope

The formal campaign evaluates 18 preselected fields, with five repetitions for
each of two certified variants (`LB0_CERTIFIED` and `LB1_MST_CERTIFIED`):
18 × 5 × 2 = 180 records. `formal_runs.csv` contains full end-to-end timings:
bound acquisition, sorting, complete downstream work, and Python/subprocess
overhead. The environment manifest records the pinned inputs, executable
fingerprints, and exact executed-script SHA-256.

The point estimate is the ratio of sums of fieldwise median wall times
(LB1/LB0 = 0.9500468834668641). A field-cluster percentile bootstrap with
10,000 resamples and seed `20261011` gives a 95% interval of
[0.8646302190056946, 1.072934097005096]. Complete Route+Path calls are 225
for LB1 and 355 for LB0. Because the interval spans 1, this campaign does not
establish an end-to-end speedup.

This is a separate campaign from the original public runtime evidence. It
supports the matched call-count comparison under the recorded conditions; it
does not expand the original benchmark scope or establish a general runtime
claim.

## Verification

The original, exact executed analysis script is retained unchanged as
`CLBOS_M2_PAIRED_TIMING.py`. To regenerate its analysis from the raw CSV:

```bash
python3 CLBOS_M2_PAIRED_TIMING.py analyze --input formal_runs.csv
```

`CLBOS_M2_INDEPENDENT_VERIFY.py` is a standard-library-only, independent
row-level checker. It validates the protocol, hashes, 180 keys, field
summaries, and bootstrap result, then writes
`CLBOS_M2_INDEPENDENT_RECOMPUTED.json`.

```bash
python3 CLBOS_M2_INDEPENDENT_VERIFY.py
sha256sum -c SHA256SUMS.txt
```

`formal_runs.csv` is retained with Windows CRLF line endings.
