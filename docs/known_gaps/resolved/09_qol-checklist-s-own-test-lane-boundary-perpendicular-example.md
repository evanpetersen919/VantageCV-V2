### [RESOLVED] QOL checklist's own `test_lane_boundary_perpendicular` example asserts the wrong property — Phase 2
QOL_RESEARCH_CHECKLIST.md Section B.2 gives an example test asserting the
*boundary polyline's own segment direction* is perpendicular to the
*centerline's segment direction* (`dot(c_dir, l_dir) ~ 0`). Verified
empirically against a correct parallel-offset boundary implementation:
the actual dot product comes out ~0.9999 (nearly parallel), not ~0 --
which makes sense, since a road's edge line runs *alongside* its
centerline, not perpendicular to it. This is a bug in the checklist's own
example, not in the implementation. `math_utils.py`'s
`compute_lane_boundaries` and its tests (`test_math_utils.py`) implement
and check the actually-correct properties instead: the boundary is
parallel to a straight centerline, and the *offset vector* (boundary
point minus centerline point) is perpendicular to the local direction at
unambiguous (endpoint) points.

