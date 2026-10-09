### [RESOLVED] `TriangleGrid.closest_hit` silently dropped real hits on flat/coplanar geometry -- found via a genuine cross-platform CI failure
First push of `TriangleGrid` passed every test locally (Windows) but
`test_lidar_hit_points_lie_on_ground_plane` failed on GitHub Actions'
Ubuntu runner: `assert len(points) > 0` got `0`. Per this project's own
standing rule, the real CI log was pulled (pasted by the user, since this
environment's `gh` isn't authenticated and the Actions logs API returns
403 without admin rights) rather than guessed at -- and reproducing the
exact failing scan locally revealed the bug was real and
platform-*independent*, just triggered by different rays on Windows vs
Linux (1 of the scan's 3 elevation rings failed locally too; Linux's
`libm` cos/sin gave slightly different values that pushed more rings over
the same edge).

Root cause: a mesh entirely at one z value (a flat ground/road plane --
extremely common in this codebase) collapses the grid's own z-extent to
a single thin cell, so the geometry sits exactly on that cell's boundary.
`closest_hit` was checking each candidate triangle hit against `t_max`,
a bound computed from the grid's own AABB-slab-intersection formula --
a *different* formula from the Moeller-Trumbore ray-triangle math that
produced the actual hit distance. For a ray grazing that shared
boundary, the two formulas can disagree by a few ULPs, and when the
triangle-intersection result came out numerically *larger* than the
AABB-derived bound, the real hit was rejected by `hit <= t_max` even
though it was the closest (only) geometry there.

Fix: separated two bounds that had been conflated. `traversal_limit`
(from the grid's own AABB math) now only governs when to stop visiting
*new* cells; `accept_limit` (the caller's own `max_distance`, or
unbounded) is what a *found* triangle hit is actually checked against.
A hit discovered while testing a cell the traversal already legitimately
visited is accepted on the caller's own terms, not rejected against the
grid's internal, approximate bookkeeping. Added a regression test
(`test_triangle_grid_finds_hits_grazing_flat_scene_boundary`) pinning
the exact failing scan config, and strengthened
`test_lidar_hit_points_lie_on_ground_plane` from `len(points) > 0` to an
exact expected count, so a partial regression (some but not all rays
affected, as happened here) fails loudly instead of slipping through a
weaker assertion again.

