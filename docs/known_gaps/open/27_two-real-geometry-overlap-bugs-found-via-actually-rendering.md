### [RESOLVED] Two real geometry-overlap bugs found via actually rendering a scenario in UE5, not any prior unit test
Both bugs existed since Phase 1-2 and were invisible to every prior test
in this codebase -- every existing overlap/setback test checked
buildings against road *centerlines* or fixed distances, never against
the real, rendered lane-mesh geometry. They were only found by
literally looking at a rendered scenario in a live UE5 editor tonight
(see the UE5 integration entries elsewhere in this file) and asking
"why does the road look staticky and why do buildings clip through it."

**Bug 1: lane geometry overlapped itself at every intersection.**
`lane_topology.py`'s `_generate_lanes_for_edge` offset each edge's full,
untrimmed centerline into lanes -- every edge meeting at a shared node
extended its lane boundaries the entire way to that exact point, with
no clipping. Quantified on a real generated `urban_dense` scenario (128
edges, 25 nodes): **3,538 overlapping lane-mesh pairs, totaling 96,319
sq m of overlap out of the scenario's 250,000 sq m total area (~38% of
all ground area)**. This is what rendered as a "staticky"/noisy-looking
road surface in UE5 -- real z-fighting between overlapping coplanar
meshes, not a rendering bug.
**Fix**: `LaneTopologyGenerator._compute_node_clearance` computes, per
node, the widest connecting road's own lane half-width
(`num_lanes * LANE_WIDTH_METERS`, max over every edge touching that
node); `_generate_lanes_for_edge` now trims each edge's effective
centerline short of both endpoint nodes by that amount (capped at 40%
of the edge's own length, so a short edge can't be trimmed to zero/
negative length) before offsetting lanes from it. Reduced overlap to
963 pairs / 55,019 sq m (a 72%/43% reduction) -- **not fully
eliminated**: a uniform per-node trim can't fully clear intersections
where two edges meet at a sharp/near-parallel angle, since their lane
strips still run alongside each other for a stretch beyond the trim
point. A real fix for that needs an angle-aware miter/wedge computation
per intersection, real additional scope not attempted here. There was
also a visible unpaved gap at every intersection (no actual junction/
intersection surface mesh was generated to fill it) -- **since fixed,
see the "[RESOLVED] Paved intersection surface" entry below.**

**Bug 2: buildings could stand inside a multi-lane road's actual pavement.**
`building_placement.py`'s `_too_close_to_road` enforced only
`config.road_setback_meters` (a small fixed margin -- 2.0m/4.0m for
this project's templates) from the road *centerline*, but a road's real
physical half-width from centerline is `edge.num_lanes *
LANE_WIDTH_METERS` (up to 14m for a 4-lane edge) -- the fixed setback
never accounted for that. Quantified on the same real scenario: **194
of 283 buildings (~69%) overlapped real lane-mesh geometry, totaling
11,615 sq m**. This is what rendered as buildings visibly clipping
through the road surface in UE5.
**Fix**: the setback enforced against each road segment is now
`config.road_setback_meters + edge.num_lanes * LANE_WIDTH_METERS`
(computed per-edge, since different edges can have different
`num_lanes`), not a single global value. Verified **fully resolved** on
the same scenario: 0 buildings overlap real lane geometry after the
fix (down from 194). Building count per scenario drops accordingly
(283 -> 83 on this seed) since the wider effective setback leaves less
usable space per block -- an expected, honest tradeoff of placing
buildings a realistic distance from actual road pavement, not a
regression.

Both fixes verified against real, rendered geometry (via Shapely,
unioning actual mesh triangles -- not a reimplementation of the same
formula the bugs were in) in new regression tests:
`test_lanes_are_trimmed_short_of_intersections`,
`test_no_building_overlaps_actual_lane_pavement`. Full test suite (442
tests) and lint remain clean.

