### [BLOCKER-for-later] Delaunay-based `RoadNetworkGenerator` cannot handle (near-)collinear node layouts — breaks the Highway scenario category
Discovered while chasing a coverage gap in Phase 1: `scipy.spatial.Delaunay`
raises `QhullError` ("Initial simplex is flat") whenever all input points are
exactly collinear, which `road_network.py::_connect_nodes` now catches and
re-raises as `ValueError` (see `test_collinear_points_raise_value_error_not_qhull_error`
in `tests/unit/test_road_network.py`).
**Why this matters**: MASTER_PROMPT Section 1.3 Category 3 (Highway) is
explicitly defined as "only parallel edges (no intersections)" — i.e.
nodes laid out in straight lines. The current grid-perturbation step adds
Gaussian noise that makes *exact* collinearity astronomically unlikely, so
generic urban-style bounds/config won't hit this — but a straight highway
segment's own generation logic (not yet written; belongs later in Phase 1
scenario-type-specific generation or Phase 2) will need either (a) a
non-Delaunay connectivity strategy for parallel/highway layouts, or (b) a
guaranteed transverse jitter large enough to keep Qhull's simplex
non-degenerate while staying visually "straight."
**Action**: do not reuse generic `RoadNetworkGenerator._connect_nodes`
unmodified for `ScenarioType.HIGHWAY` without addressing this. Revisit when
implementing scenario-type-specific road generation.

