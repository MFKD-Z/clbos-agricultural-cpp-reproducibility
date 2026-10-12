# S7 pinned-planner polyline semantics and Proposition 1 implementation closure

Created 2026-10-12T10:23:31.310211+08:00 (Asia/Shanghai). This is an independent, read-only analysis of the pinned production source and six existing observations. No planner case was rerun. Original strict S7 `FAIL` and A3 root-cause files remain unchanged.

## Decision

```text
TASK_STATUS=PARTIAL
A1_IMPLEMENTATION=INCONCLUSIVE
A2_IMPLEMENTATION=INCONCLUSIVE
A3_STRICT_CONTINUITY=FAIL
A3_POLYLINE_SEMANTICS=PASS
A4_IMPLEMENTATION=INCONCLUSIVE
SAME_GROUP_MULTISWATH_BRANCH=EXCLUDED
SPECIAL_CONNECTION_BRANCHES=INCONCLUSIVE
MST_RELAXATION_MAPPING=PASS
PROPOSITION1_IMPLEMENTATION_SCOPE=CONDITIONAL_ONLY
S7_ORIGINAL_GATE=FAIL
S7_REFINED_POLYLINE_GATE=INCONCLUSIVE
SOURCE_LEVEL_PROOF_COMPLETE=FALSE
RUNTIME_EVIDENCE_COMPLETE=FALSE
SCIENTIFIC_METHOD_CHANGED=FALSE
```

The charged sampled-polyline interpretation passes in the **44 observed required inter-swath connectors**, while the `PathState::atEnd()` interpretation fails in all three multi-swath cases. This distinction explains the earlier 25 µm A3 result; it does not close the implementation-wide proof. A1, A2 and A4 are supported by these six observations but are not source-enforced for every input. The refined gate is therefore INCONCLUSIVE, and the original gate stays FAIL.

## Frozen identity and text scope

Fields2Cover HEAD `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`, clean source worktree. Production adapter SHA-256 `348a227182252feb63743fb9cd711fec6dd0a57ce7891b99dda3db4d1ab23658`; original execution binary `4c89a57f2ffe4d1bd00f42e7743936297217cb2e91971062eaf61f3046712f4c`; linked Fields2Cover library `1338ade681056f031806bb1349f3a5cd5392e614a00c5fac3170ec7f3574ceda`. Original audit and A3 follow-up hashes agree with their manifests. The latest JESTECH Section 2.2, Proposition 1, Table 1 and S7 text are still unavailable locally: **JESTECH_TEXT_ALIGNMENT=UNVERIFIED**. The accessible Biosystems Engineering manuscript is related material, not an authenticated substitute. This report diagnoses the frozen operational definitions only.

## Complete fixed-path call chain

`s7_source_callchain.csv` gives absolute paths, functions, line ranges, calls, branch conditions, object flow, length geometry and unverified risks. In brief: the production adapter reads metric WKT, makes 3m + 3m headlands, generates fixed-angle BruteForce swaths and obtains `SwathLength`; `genRoute` builds coverage/shortest graphs and transforms solver node IDs to Route groups; `Route::addSwath(s,g)` makes a new connection before each later swath; `planPath` appends each connection and each swath; `DubinsCurves::createSimpleTurn` produces steering samples; `steerStatesToPath` uses successive-sample chord lengths; `Path::appendSwath` uses successive swath-vertex distances; `Path::operator+=` appends without geometric checks; `PathLength::computeCost` inherits `PPObjective::computeCost`, which returns the sum of `fabs(PathState.len)`. The adapter returns that positive finite total as `complete_path_length_m`.

The `PathPlanning::planPath(swaths)` branch that calls `turn_path.discretize(0.1)` requires a group with more than one swath. It is **source-proven excluded for this exact adapter path**: `transformSolutionToRoute` only calls `Route::addSwath(swath, shortest_graph)`; on a nonempty route this calls `addConnection`, and `Route::addSwath(swath)` then opens a new group because the connection count exceeds the old group count. The adapter never calls another Route mutator. The six observations independently have one swath per group. Thus `Path::populate/reduce`, reached through same-group `discretize`, do not explain these observations. They remain relevant to other callers that construct a Route differently.

## A3-STRICT versus charged sampled polyline

The 48,085 previously recorded 1e-6m strict gaps are all TURN→TURN. In the fixed source, `steerStatesToPath` stores each steering sample's position and tangent heading but sets `len` to the distance to the next sample; `PathState::atEnd()` moves along the heading by `len`. The reconstructed endpoint can therefore miss the next point on a curve. The original strict A3 result remains FAIL.

For the charged-polyline audit, a nonworking state represents the ordered edge from its `point` to the **next final PathState's `point`**, including zero-length terminal states at subturn boundaries. Every one of the 57,132 observed nonworking states belongs to exactly one of 44 required connector ranges. Every connector starts and ends at the neighbouring swath endpoints within 1e-06m (maximum observed endpoint error 0m). For every state, `fabs(len)` matches that next-sample chord within the original S7 numeric comparison tolerance (absolute 1e-06m plus relative 1e-10); maximum individual residual 1.35e-09m, maximum connector total residual 1.1e-09m. All 141 zero-length nonworking states have zero next-sample displacement. No observed nonworking segment is unpaid or assigned to two connectors. All observed PathDirection values are +1; 28 route swaths reverse their **geometric vertex order**, which `appendSwath` still charges forward. Vehicle backward motion remains unobserved.

The interpretation is conditional: the source computes turn `len` before `TurningBase::correctPath` may move the first or last sample by up to 0.05m without recomputing `len`; and `createTurn` can return an empty Path when it has at most one state. Neither can be dismissed by calling `Path::length`. These branches are listed in `s7_branch_coverage.csv` with their actual source reachability and runtime evidence.

## Why the endpoint MST is a relaxation

The sidecar `agri_f2c_mst_probe.cpp:102-148` flattens **all generated swaths**, creates a complete graph with one vertex per swath, and assigns edge weight `w(i,j)` as the minimum of the four Euclidean endpoint-pair distances. Prim's algorithm adds the least reachable edge until all vertices are used; for `n≤1` its connection bound is zero. It adds this MST to the same generated swath length used by LB0. Independent reconstruction from the six serialized generated-swath lists matches the frozen LB1 within 2.27e-13m.

Suppose each mandatory swath occurs in the charged path and the distinct required connections form a connected swath-visitation walk. For a connection from endpoint `p` of swath `i` to endpoint `q` of `j`, `w(i,j)≤||p−q||`. If its charged sampled-polyline length is the sum of all consecutive sample chords and samples start at `p` and end at `q`, the triangle inequality gives `||p−q||≤charged_length`. A connected walk contains a spanning tree, so `MST≤sum(required connector charges)`. The complete graph and minimum over all endpoint pairs impose **weaker**, not stronger, constraints than the realised route; depot or extra nonworking costs are not needed in the MST and can only add to J when nonnegative. With A1, A2 and A4, `LB0≤LB1≤J`. This mathematical mapping is valid for the stated predicates, independent of route optimality. It is not a source proof that every returned finite plan satisfies those predicates.

In the three observed multi-swath cases, each connector's charged state length exceeds its endpoint straight-line distance; the smallest connector surplus is 2.995825883m. All six frozen LB0/LB1 values agree with the independently reconstructed generated swaths and satisfy `LB0≤LB1≤J`; the smallest multi-swath `J−LB1` is 10.062811315m. The finite orientation domain permits an admissible bound-based stop **only if each unevaluated candidate's bound is valid and execution failures remain unresolved as specified**. Numerical success on these six does not prove that premise for the other 127 S7 keys or for all possible inputs.

## Proof obligations and branches

`s7_proof_obligation_matrix.csv` separates mathematical predicates, source support, runtime evidence and the remaining gap. `s7_branch_coverage.csv` uses `SOURCE_PROVEN_EXCLUDED`, `SOURCE_SUPPORTED`, `RUNTIME_VERIFIED` and `UNRESOLVED`. The important unresolved conditions are: the route conversion matches swaths by endpoint coordinates and takes the first match without asserting a one-to-one generated-swath mapping; `TurningBase::createTurn` may return empty; endpoint correction may alter charged chords; positive finite J is checked without a full coordinate, coverage or connection audit. Those are **source-level proof gaps**, not observed planner failures. No new candidate was selected to force a PASS; no planner was rerun.

## Scientific closure and minimal text changes

**A sentence-only replacement of A3 does not close Proposition 1 for the pinned implementation.** The mathematical proposition can be stated with a charged-polyline A3 condition, but the implementation-wide claim still needs a checked one-to-one swath mapping, a charged connector for every required adjacency, endpoint and per-edge charge validation after `correctPath`, and complete handling of empty/nonfinite paths. The 127 unrun S7 cases and latest JESTECH text also remain open. Without those checks or a source proof, the correct manuscript scope is conditional, not an unconditional guarantee about this implementation.

Suggested sentence-level wording for later author review (no Word file edited):

1. Replace the strict A3 sentence with: “For each valid finite plan to which the bound is applied, every generated working swath is included in one connected ordered traversal, and each required inter-swath connection is represented by an ordered sequence of sampled points whose first and last points coincide with the corresponding swath endpoints; the charged nonworking length of that connection is no less than the sum of Euclidean distances between consecutive samples.”
2. Add immediately after it: “The fixed implementation's `PathState::atEnd()` need not equal the next state's stored point at every Dubins sample; any implementation claim based on sampled-point connectivity requires explicit verification of swath inclusion, connector endpoints, charged chord lengths and absence of uncharged jumps for the evaluated candidate.”
3. Qualify the Proposition 1 implementation sentence as: “Under A1, A2, the charged-sampled-polyline form of A3, and A4 for every candidate on the predefined finite orientation domain, the endpoint-minimum complete-graph MST is an admissible connection lower bound; candidates with unresolved planning outcomes are not certified by this statement.”

These are **proposed conditions**, not claims already verified for all runs. They do not change the scientific method or retroactively pass the original strict A3 audit.
