### [RESOLVED] Ground truth extraction only covered buildings, not vehicles/pedestrians
Was: `bbox_3d.py`, `bbox_2d.py`, and `segmentation.py` all operated on
`Building` objects only -- no vehicle/pedestrian placement existed
anywhere in the pipeline, and MASTER_PROMPT never specifies one for any
phase (`ScenarioTypeConfig.vehicle_mix` since Phase 1 and
`TrafficNetworkGenerator`'s driving/pedestrian `SpawnZone`s since Phase 3
both sat unused for their obvious purpose until now).

Resolved by adding `src/procedural/actor_placement.py`
(`ActorPlacementGenerator`): places vehicles/pedestrians at
`TrafficNetworkGenerator`'s own spawn zones (one occupancy roll per zone,
sampled from `config.traffic_density`; vehicle type sampled from
`config.vehicle_mix`; heading derived from the spawn zone's own road
edge direction), with AABB-overlap rejection between vehicles.
`BoundingBox3D` gained `heading_rad` (a real rotation applied in
`corners()`, not just axis-aligned) and `category_id`
(`src.ground_truth.categories`, shared with `coco_exporter.py` so the two
can't drift). `MeshFactory` gained `build_vehicle_mesh`/
`build_pedestrian_mesh` (oriented boxes, same topology as
`build_building_mesh`). `dataset_generator.render_frame` combines all
three object kinds' `BoundingBox3D`s with an id-offset scheme (each
kind's own 0-based counter offset by the preceding kinds' counts) so
`object_id` stays globally unique per frame.

Three deliberate scope decisions made along the way, not covered by any
spec (MASTER_PROMPT never specifies vehicle/pedestrian placement at all):
- **Pedestrian occupancy** is `traffic_density`'s own sampled fraction
  times a fixed `PEDESTRIAN_DENSITY_FRACTION_OF_TRAFFIC = 0.3` constant,
  since `ScenarioTypeConfig` has no dedicated pedestrian-density field
  and adding one for a single module felt like the wrong place to extend
  the schema.
- **No bounds-containment check** for vehicles/pedestrians in
  `ScenarioValidator` (only finiteness) -- unlike buildings, which get an
  explicit `ROAD_SETBACK_METERS` margin *guaranteeing* their footprint
  stays inside `bounds`, vehicles/pedestrians are anchored directly at
  spawn zone positions, which are themselves never bounds-checked (see
  `test_traffic_network.py`) and can legitimately sit at/past the road
  network's edge. Adding a strict check here surfaced this immediately
  as real end-to-end generation failures, not a false positive to
  special-case around.
- **Vehicles/pedestrians are represented as boxes still** for meshes (no
  wheels/limbs/detail) and are static (no motion, no lane-following
  behavior) -- placement only, matching this phase's actual scope.
  Per-lane turn connectivity (needed for real vehicle *navigation*, as
  opposed to placement) remains deferred -- see that entry below.

Road/lane ground truth (as opposed to vehicles/pedestrians) is still not
extracted -- nothing in MASTER_PROMPT's Phase 5 bullets asks for it, and
roads/lanes aren't "objects" in the AV-perception sense a COCO category
would represent.

