### [RESOLVED] Pedestrians were walking 90 degrees off the sidewalk, and standing at road level not sidewalk level
User asked for a deep, evidence-based analysis of pedestrian rotation
and physical placement, explicitly rejecting any guessed correction --
two real, previously-undetected bugs found by actually verifying rather
than assuming the existing math was correct.

**Bug 1, real and significant**: every pedestrian was facing/walking
90 degrees off the real sidewalk direction. `heading_rad` (and, until
now, the rendered `rotation_rad`) used `atan2(dy, dx)` -- the correct
formula for every OTHER asset in this project (vehicles, curbs,
corners, facade pieces), all of which are authored with their own local
+X axis as their "forward"/"along-the-run" direction. Verified live,
rigorously, with the same two-orthogonal-axis-aligned-camera technique
already used for corner-piece rotation work: a camera looking along the
python Y axis at `rotation_rad = 0` showed the character's BACK (not a
front/back match for a local+X-forward asset); a second camera looking
along the python X axis showed a clean SIDE PROFILE (ruling out local
+X as forward -- a local+X-forward mesh would show a front/back view on
this axis instead). Conclusion, confirmed by two independent clean
shots: this specific VAT mesh's own walking/facing direction is
authored along its local **+Y** axis, not +X, unlike everything else in
this codebase.

Derived the fix algebraically, not by trial and error: solving
`local+Y -> (dx, dy)`, i.e. `(sin r, -cos r) = (dx, dy)`, gives
`r = atan2(dx, -dy)`, which is identically `atan2(dy, dx) + pi/2` for
every direction (verified with several cases). New
`PEDESTRIAN_MESH_FORWARD_OFFSET_RAD = pi/2` (`city_sample_assets.py`)
applied ONLY when computing the rendered `rotation_rad`
(`scenario_serializer.py`'s `_pedestrian_to_asset_json`) -- `Pedestrian.
heading_rad` itself stays the real physical direction-of-travel value
(matching the edge/sidewalk direction) for ground truth, deliberately
uncorrected by this mesh-authoring quirk, same separation of concerns
`traffic_lights.py`'s own `+pi` mast-arm offset already established.
Live-verified twice: an isolated test at `heading_rad = 0` (equivalent
to "walking along +x") now shows the character's FRONT facing +x
instead of a side profile; a real generated scenario shows multiple
pedestrians walking parallel to the curb/sidewalk direction, in profile
relative to the road, not facing into it or at a random angle.

**Bug 2, real and simple**: pedestrian z was hardcoded to 0.0 (the flat
road surface height), same as a vehicle -- but pedestrians are placed on
the SIDEWALK, which sits measurably higher than the road
(`road_edge_kit.py`'s own documented, real 10.8cm sidewalk-top height
above the road crown -- now exported as `SIDEWALK_TOP_HEIGHT_METERS`).
Confirmed both migrated pedestrian meshes are pivoted at their own feet
(via `GetStaticMeshBounds`: vertical extent starts at ~0cm for both),
so their z position needs to equal the real sidewalk height directly,
not 0. Fixed: pedestrian z is now `SIDEWALK_TOP_HEIGHT_METERS`.
Live-verified via `DebugListActorsWithMesh` on a real generated scenario:
every pedestrian actor's real world Z is exactly `10.800`, and the
same screenshot confirms they visually stand flush on the sidewalk
surface, not sunken into the road plane.

Full suite green (557/557) after updating `test_scenario_serializer.py`
for the new position/rotation values.

