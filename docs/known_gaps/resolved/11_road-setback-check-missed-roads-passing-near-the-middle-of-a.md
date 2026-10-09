### [RESOLVED] Road setback check missed roads passing near the *middle* of a building's side — Phase 2
While fixing the above, restricting the setback check to only a block's
own 3 triangle edges (for speed) caused `test_no_building_within_road_setback`
to actually fail: a building's corner came within 1.81m of a road,
violating the 2.0m `ROAD_SETBACK_METERS`. Root cause: for a
skinny/obtuse Delaunay triangle, a road segment that is *not* one of that
triangle's own 3 edges can still pass within the setback distance of a
point deep inside it. Fixing that (checking every real road segment,
spatially pre-filtered by a cheap padded-AABB test for speed) then
exposed a second, independent bug: the setback check itself only tested
distance from the building footprint's 4 *corners* to each road segment,
which misses a road running near-parallel to, and close beside, the
*middle* of one of the footprint's sides -- confirmed as the actual cause
of `test_no_building_to_building_overlap` failing (two buildings on
opposite sides of a shared road overlapped because neither one's corners,
specifically, were close enough to trip the corner-only check). Fixed by
replacing the corner-distance check with `_segment_intersects_aabb`
(slab-method segment-vs-box intersection) against the footprint's AABB
inflated by the setback distance -- the geometrically correct formulation
of "does anything about this road come within `ROAD_SETBACK_METERS` of
this box." Both tests now pass; see
`test_segment_intersects_aabb_near_parallel_to_one_side` for a test that
specifically reproduces the missed case.

