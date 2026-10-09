### [RESOLVED] LiDAR ray-casting and depth-map rendering had no spatial acceleration structure
Was: `lidar_model.py`'s `LidarSensor.scan` and `depth_map.py`'s
`render_depth_map` were both O(rays * triangles) / O(pixels * triangles)
brute force -- every ray tested against every triangle of every mesh,
with tests kept deliberately small specifically because of this.

Resolved by `lidar_model.py`'s `TriangleGrid`: a uniform 3D grid built
once per scene (triangles binned into cells sized so each holds roughly
`target_triangles_per_cell` on average), then queried per ray via
Amanatides & Woo's 1987 voxel-traversal algorithm -- a ray only tests
triangles in the cells it actually passes through, walked in distance
order with early termination the moment a found hit is closer than the
next unvisited cell could possibly contain anything. This is an *exact*
acceleration structure, not an approximation: verified directly (200+
randomized scenes/rays plus explicit axis-aligned-ray and
`LidarSensor.scan`-level cases in `test_lidar_model.py`) to return
bit-identical results to the brute-force `closest_hit_distance` on the
same scene. `closest_hit_distance` itself is kept as the simple
reference implementation (and as what `TriangleGrid` is verified
against) but is no longer on either module's hot path -- both
`LidarSensor.scan` and `render_depth_map` build one `TriangleGrid` and
reuse it across every ray of the sweep/image, rather than rebuilding
(or re-scanning every triangle) per ray.

One subtlety worth recording: `LidarSensor.scan` only passes
`max_range_m` as the grid's search cutoff when `range_noise_std_m == 0`.
With noise enabled, a *true* hit just beyond `max_range_m` can still be
reported if noise happens to pull the measured range back within range
(a real noisy sensor could do the same) -- bounding the search to
`max_range_m` in that case would silently make such hits impossible to
find at all, changing behavior rather than just accelerating it.
**Action**: none -- `depth_map.py`'s `render_depth_map` has no analogous
range cutoff to worry about, so it always passes no `max_distance` limit.

