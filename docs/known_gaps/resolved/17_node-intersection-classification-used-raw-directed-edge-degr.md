### [RESOLVED] Node/intersection classification used raw directed-edge degree instead of road-connection count — Phase 1
Found while investigating a coverage gap (the `degree == 3` T-junction
branch was never hit by any test). Root cause: every road is always
created as a *bidirectional pair* of directed edges
(`_create_edge_pair`), so `len(incoming_edges) + len(outgoing_edges)` is
**always even** for every node — the master prompt's own
`degree == 3 -> T_JUNCTION` condition is therefore mathematically
unreachable, and its `degree >= 4 -> FOUR_WAY` condition silently
mislabels genuine 3-way intersections (which have degree 6) as four-way.
Confirmed empirically: sampling degrees across a generated network showed
only even values (4, 6, 8, 10, ...), never 3. Fixed in
`_assign_road_attributes` by classifying on `degree // 2` (the actual
number of distinct connected roads) instead of raw degree. Added
`test_three_way_junction_classified_as_t_junction` and strengthened
`test_node_types_assigned_correctly` to assert degree is always even before
halving it. This also changes `_assign_road_attributes`' lane/speed
heuristic, which used the same (buggy) raw-degree comparison for its
`start_degree >= 3` branch.

