# Independent runner and probes

These C++ sources link against an external Fields2Cover checkout at the pinned revision. They encode the experiment's robot and planner configuration: 2 m robot width, 2 m coverage width, 6 m body-length protocol binding (not consumed by the Fields2Cover path planner), 2 m minimum turning radius, a fixed 6 m headland construction, trapezoidal decomposition, brute-force swath generation with SwathLength, RoutePlannerBase, and Dubins path planning.

The `RunnerSafeTrapezoidalDecomp` fallback handles a post-split numerical buffer that returns multiple polygon components. It is an adapter-layer compatibility fallback; it does not patch Fields2Cover. The normal path preserves stock Fields2Cover behavior, while the fallback retains all polygon components instead of forcing an invalid single-cell conversion.

`CMakeLists.txt` expects `F2C_SOURCE_DIR` to point to the separately cloned Fields2Cover source. Build out of source. The full runner performs Route+Path evaluation; the probes expose lower-bound stages and can also perform downstream evaluation depending on flags. They are not called by Level A verification.
