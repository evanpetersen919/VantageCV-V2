### [RESOLVED] Lane connectivity across intersections was not implemented
Was: deferred twice -- Phase 2's `lane_topology.py` deferred it to Phase
3's traffic rules; Phase 3's `traffic_network.py` deferred it again
("full per-lane turn graphs are deferred further still"), since neither
phase had (or needed) the geometric classification logic to determine
which incoming lane legally feeds which outgoing lane at an intersection.

Resolved by `src/procedural/lane_connectivity.py`
(`LaneConnectivityGenerator`): for every (incoming edge, outgoing edge)
pair at a node (from `RoadNode.incoming_edges`/`outgoing_edges`, already
populated since Phase 1 but otherwise unused for this purpose), classifies
the movement STRAIGHT/LEFT/RIGHT from the signed angle between the
incoming edge's final heading and the outgoing edge's initial heading,
excludes U-turns (`outgoing_edge is incoming_edge.reverse_edge_id`), and
drops LEFT/RIGHT movements the incoming edge's own
`allows_turning_left`/`allows_turning_right` flag forbids -- both fields
existed, unused, since Phase 1 too. Lane-level (not just edge-level)
mapping follows `lane_topology.py`'s own right-hand-traffic convention
(lane 0 = median/left lane, highest index = curb/right lane): STRAIGHT
connects lanes index-for-index, LEFT only connects lane 0 to lane 0,
RIGHT only connects the outermost lane to the outermost lane -- a
defensible default absent any dedicated-turn-lane concept elsewhere in
this codebase.

Wired into `ScenarioResult.lane_connectivity` and `ScenarioValidator`
(basic regression checks: every connection's lane ids are real, no
lane connects to itself) alongside every other generator's output.
Deliberately still out of scope: this produces a connectivity *graph*
(which lane can legally reach which), not vehicle routing/path-following
behavior -- `ActorPlacementGenerator` still places vehicles statically at
spawn zones; nothing consumes this graph to actually move a vehicle
through an intersection yet. Revisit if/when vehicle animation/routing
is ever built -- this graph is exactly what that would need as its input.

