### [RESOLVED] Forward/reverse road edges got independently-sampled, often-mismatched lane counts — found in Phase 3
QOL_RESEARCH_CHECKLIST.md Section G.1's own `test_lane_count_consistent`
asserts a directed edge and its reverse counterpart must have the same
`num_lanes`. Checked directly against Phase 1's `_assign_road_attributes`
(unchanged since Phase 1, not previously tested for this property): 76 of
118 edges in a routine urban_dense/500m test scenario had mismatched
forward/reverse lane counts, road types, and speed limits, because the
master prompt's reference implementation (and this codebase's Phase 1
port of it) samples each directed edge's attributes independently. Fixed
in `road_network.py::_assign_road_attributes` by computing attributes
once per undirected road and applying them identically to both directed
edges of a bidirectional pair, tracked via a `processed_edge_ids` set.
Added `test_forward_reverse_edge_attributes_match` as a regression test.
This mattered enough to fix now (rather than deferring) because Phase 3's
`TrafficNetworkGenerator` builds spawn zones and a navigation graph
directly on top of `num_lanes`/`speed_limit_kmh` -- building on
inconsistent data would have baked the bug one layer deeper.

