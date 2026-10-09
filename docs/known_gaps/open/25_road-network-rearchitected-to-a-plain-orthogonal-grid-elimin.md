### [RESOLVED] Road network rearchitected to a plain orthogonal grid -- eliminates the remaining lane-overlap z-fighting entirely
Follow-up to the "[RESOLVED] Two real geometry-overlap bugs" entry
below: that entry's lane-trim fix reduced overlap by 72%/43% but
explicitly couldn't reach zero, because a uniform per-node trim can't
fully clear intersections where two edges meet at a sharp/near-parallel
angle -- and the road network at the time (perturbed-grid + Delaunay
triangulation) could and did produce arbitrary-angle intersections,
including acute ones.

Root-caused via a deliberate design decision, not a further patch:
`src/procedural/road_network.py` was rearchitected from
perturbed-grid + Delaunay triangulation to a plain orthogonal grid --
every node connects only to its immediate +x/-x/+y/-y grid neighbor, so
every intersection is a clean 90-degree crossing. This makes the
existing per-node lane trim (`LaneTopologyGenerator._compute_node_clearance`)
mathematically exact instead of a partial mitigation: perpendicular
roads trimmed back by their own half-width geometrically cannot
overlap. **Verified on the same real scenario shape used throughout
this investigation: 0 overlapping lane-mesh pairs (down from 3,538
originally, 963 after the trim-only fix)** -- confirmed via real mesh
geometry (Shapely), not reasoning about the algorithm. New regression
test: `test_no_lane_overlaps_at_intersections`.

**Real cost, not free**: this removes organic/arbitrary-angle street
variety -- a real, explicit tradeoff, not an oversight (see
road_network.py's own module docstring for the full reasoning).
Diagonal roads may be added back later as an explicit, additional
connection strategy layered on top of the grid, not a revival of the
old point-cloud/Delaunay approach.

**Real downstream consequences, both handled, not just noted**:
1. `building_placement.py`'s `_identify_blocks` used to re-triangulate
   node positions internally (its own separate Delaunay call) and keep
   only triangles whose 3 edges all survived length-filtering. With no
   diagonal edges left in the road graph at all, every such triangle
   failed that check -- **zero blocks, zero buildings placed**, a real
   break caught immediately by the existing test suite (5 tests failed
   with "assert []"), not silently shipped. Fixed by replacing
   triangle-based block *approximation* with exact rectangular
   grid-cell identification (reconstructing rows/columns purely from
   node positions, since this module only receives the generic
   `nodes`/`edges` dicts, not `RoadNetworkGenerator`'s internal grid
   array) -- genuinely more correct, not just a workaround, since real
   city blocks in a grid city are rectangles, not triangle
   approximations.
2. Several `road_network.py`/`test_road_network.py` tests were tied
   directly to the removed Delaunay/perturbation machinery
   (`_find_or_create_node`'s merge-by-distance behavior,
   `QhullError`-wrapping for collinear points) and were removed, not
   just left failing -- that functionality no longer exists, so testing
   it would be testing dead code.

Full test suite (441 tests) and lint clean after all of the above.

