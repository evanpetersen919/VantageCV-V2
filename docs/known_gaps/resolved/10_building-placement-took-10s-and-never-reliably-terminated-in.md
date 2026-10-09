### [RESOLVED] Building placement took >10s and never reliably terminated in reasonable time — Phase 2
First implementation of `BuildingPlacementGenerator.generate` hung for
over a minute on a routine urban_dense/500m bounds test case (confirmed by
direct timing, not assumed). Root causes, both real and stacked: (1)
`target_count` per block sometimes reached the hundreds for a single large
triangle, and the loop paid the full `MAX_PLACEMENT_ATTEMPTS_PER_BLOCK`
cost even long after a block was effectively full; (2) every placement
candidate was checked for overlap against *every building placed in every
block so far* (`existing_buildings`), an unnecessary O(total_buildings^2)
cost across the whole scenario, not just within one block. Fixed with (1)
an early-exit after `MAX_CONSECUTIVE_FULL_FAILURES` consecutive slots each
exhaust every attempt (signal a block is full without exhausting
`target_count`), and (2) checking new candidates only against the current
block's own `placed` list -- justified because Delaunay triangle interiors
never overlap and (once the setback bug below was also fixed) no building
can cross into a neighboring block, so cross-block overlap is
geometrically impossible without an explicit check. Verified: 769
buildings generated in 0.52s post-fix vs. >60s (killed) before, on the
identical scenario.

