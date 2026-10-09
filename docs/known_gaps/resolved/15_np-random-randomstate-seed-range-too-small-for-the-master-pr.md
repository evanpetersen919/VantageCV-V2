### [RESOLVED] `np.random.RandomState` seed range too small for the master prompt's own test requirement — Phase 1
The master prompt's Section 3.2.2 `test_seed_coverage_edge_cases` requires
`seed=2**63-1` to work, but confirmed by direct test:
`np.random.RandomState(2**63 - 1)` raises `ValueError: Seed must be between
0 and 2**32 - 1`. This is a genuine bug in the master prompt's own
reference implementation, not a hypothetical. Fixed in
`RoadNetworkGenerator.__init__` by switching to
`np.random.Generator(np.random.PCG64(seed))`, which accepts arbitrary-size
non-negative integer seeds via `SeedSequence` while remaining fully
deterministic. Verified: `test_seed_coverage_edge_cases` now passes for
seeds `[0, 42, 12345, 2**32-1, 2**63-1]`.

