# S7 unresolved implementation obligations

1. **A1 global identity:** `transformSolutionToRoute` matches the first swath with a matching endpoint pair and has no unique generated-swath ID or multiset assertion. Prove one-to-one correspondence for all frozen candidate inputs, or instrument every bound-eligible full evaluation.
2. **A2 connector existence:** `createTurn` can return an empty Path. Demonstrate that this occurs only for coincident endpoints with no required travel, or reject those candidate plans.
3. **A3 charged polyline after correction:** `correctPath` may move sampled endpoints by up to 0.05m without recomputing adjacent `len`. Prove the resulting charged length still bounds the sampled connector geometry, or check each returned connector edge at runtime and apply an explicit safe policy for any residual.
4. **A4 complete ledger:** Positive finite total length does not assert that all swaths and required connectors were included exactly once. Establish a per-state disjoint ledger for every candidate used in a certificate.
5. **Exceptional states and directions:** Verify or safely reject empty/nonfinite paths, degenerate swaths, duplicate endpoints, illegal direction values and any backward vehicle motion. The observed zero-length terminal states were safe; they do not close all such branches.
6. **Candidate coverage:** Only six of 133 predeclared keys ran in S7, and only three had multiple swaths. The remaining 127 cannot be labelled passing from source plausibility or these six results.
7. **Paper alignment:** Latest JESTECH Proposition 1, Table 1 and S7 are unavailable locally. Compare exact wording against the conditional predicates before publication.
8. **Certificate failure policy:** Confirm that unresolved planner outcomes are never treated as model infeasibility or silently pruned under a bound that has not been validated for that candidate.

The complete-graph endpoint MST relaxation itself matches the six frozen bound records and is mathematically optimistic under the predicates above. The missing step is an implementation-wide proof or runtime certificate of those predicates.
