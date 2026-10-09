### [RISK] `_find_or_create_node` is O(N) per call / O(N^2) total for grid merging
Documented in its own docstring as an acceptable tradeoff at the scenario
sizes targeted (hundreds of nodes), confirmed fine by
`test_large_scenario_performance` (2000m x 2000m bounds completes well
under the 10s budget). Revisit with a `scipy.spatial.KDTree` if/when Phase
1 performance tests are run at the "10,000+ scenarios" scale mentioned in
MASTER_PROMPT's scalability requirements, or if bounds grow past ~5km.

