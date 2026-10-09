### [RESOLVED] Road network nodes could end up outside the caller's declared bounds — found via Phase 4's ScenarioValidator
Discovered by `ScenarioValidator`'s own first real end-to-end test
(`test_full_generated_scenario_is_valid`) actually failing on a routine
generated scenario: node positions up to ~70m outside a 500m-wide bounds
region. Root cause, present since Phase 1 and never previously tested:
(1) `_generate_grid_points` can overshoot the requested bounds by up to
one full grid `spacing` per axis by construction (`np.arange(x_min, x_max
+ spacing, spacing)` always includes `x_min + spacing`, previously noted
in this file only as a "grid points guaranteed >= 2 per axis" quirk, not
recognized as a bounds violation in its own right); (2) Gaussian
perturbation in `_perturb_grid` can push any point further out, with no
containment check anywhere in the pipeline. Fixed by adding
`RoadNetworkGenerator._keep_within_bounds`, called after perturbation:
reflects any out-of-bounds point back across the violated edge (not a
hard clip, which would collapse every overshooting point on the same
side onto one exact boundary line -- for 3+ points, an exactly collinear
configuration that crashes Delaunay triangulation, a real failure mode
already established via `test_collinear_points_raise_value_error_not_qhull_error`).
A final `np.clip` is kept as a safety net for the practically-unreachable
case where reflection alone isn't enough. Verified with
`test_all_node_positions_within_bounds` and a 20-seed parametrized
variant, plus the originally-failing validator integration test now
passing.

