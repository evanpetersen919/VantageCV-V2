Release Notes
==============

Unreleased -- Spatial acceleration for LiDAR/depth-map ray-casting
-----------------------------------------------------------------------

Added ``TriangleGrid`` (:mod:`src.sensors.lidar_model`): a uniform-grid
spatial index over a scene's triangles, queried via Amanatides & Woo's
1987 voxel-traversal algorithm. Closes the "no spatial acceleration
structure" gap that previously forced both ``LidarSensor.scan`` and
``render_depth_map``'s own tests to keep scenes artificially tiny (both
were O(rays * triangles) / O(pixels * triangles) brute force). An
*exact* acceleration structure, not an approximation -- verified directly
against the brute-force ``closest_hit_distance`` reference across
hundreds of randomized scenes/rays, explicit axis-aligned-ray cases, and
a full ``LidarSensor.scan``-level comparison. ``segmentation.py``'s
per-object rasterization is a different (non-ray-casting) algorithm and
remains unaccelerated -- see :doc:`architecture`.

Unreleased -- Sensor noise model
------------------------------------

Camera projection, LiDAR ray-casting, and depth-map rendering were all
perfectly noise-free; closed the gap MASTER_PROMPT's own
``camera_front.yaml``/``camera_rear.yaml`` templates implied by declaring
``distortion_model``/``distortion_coeffs`` fields nothing read. Added
``CameraIntrinsics.distortion_coeffs`` (Brown-Conrady k1/k2/p1/p2/k3,
applied in ``Camera.project`` -- ``None`` by default, so every
pre-existing caller is unaffected), ``LidarConfig.range_noise_std_m``
(zero-mean Gaussian noise on each hit's measured range, ``LidarSensor``
now takes an optional ``seed``), and ``render_depth_map``'s
``noise_std_m``/``seed`` (same Gaussian-noise treatment, applied only to
finite/hit pixels). Every noise parameter defaults to off/zero and
*requires* an explicit seed the moment it's turned on -- deterministic
noise, not silent OS-entropy randomness, matching every other generator
in this codebase. Every real sensor profile shipped in this repo uses
all-zero distortion coefficients, so this changes no default output
anywhere; it's opt-in realism for a caller that wants it. Deliberately
out of scope: pixel quantization (risks disturbing existing bbox-extraction
precision for no clearly-demonstrated benefit) and loading distortion
coefficients from ``configs/sensor_profiles/`` YAML (still reference-only,
same as the scenario templates before ``config_loader.py`` -- see
``KNOWN_GAPS_AND_ISSUES.md``).

Unreleased -- Per-lane turn connectivity across intersections
--------------------------------------------------------------

Added :mod:`src.procedural.lane_connectivity` (``LaneConnectivityGenerator``):
computes which lane legally feeds which other lane at every intersection,
closing a gap deferred twice (Phase 2's ``lane_topology.py`` deferred it to
Phase 3's traffic rules; Phase 3's ``traffic_network.py`` deferred it
again). Classifies each (incoming edge, outgoing edge) movement
straight/left/right from the signed angle between their headings,
excludes U-turns (the incoming edge's own reverse), and respects
``RoadEdge.allows_turning_left``/``allows_turning_right`` -- both fields
existed unused since Phase 1. Lane-level mapping follows
``lane_topology.py``'s own right-hand-traffic convention: straight
connects lanes index-for-index, left only connects the median (lane 0)
lane, right only connects the curb (highest-index) lane. Wired into
``ScenarioResult``/``ScenarioValidator`` alongside every other generator's
output; produces a connectivity *graph* only, not vehicle routing
behavior -- ``ActorPlacementGenerator`` still places vehicles statically.

Unreleased -- CLI + scenario config YAML loading
----------------------------------------------------

Added ``bin/generate_dataset.py``, an argparse CLI wrapping
:func:`src.orchestration.dataset_generator.generate_dataset`, and
:func:`src.utils.config_loader.load_scenario_config`, which loads a
``configs/scenario_templates/``-shaped YAML file into a
:class:`src.procedural.scenario.ScenarioTypeConfig`. Only
``urban_dense.yaml``/``urban_sparse.yaml`` are actually generatable --
:class:`src.procedural.road_network.RoadNetworkGenerator` implements one
strategy (perturbed-grid + Delaunay) regardless of ``scenario_type``, so
``highway.yaml``/``parking_lot.yaml``/``roundabout.yaml`` (different,
never-implemented strategies) raise ``NotImplementedError`` with a clear
message rather than a confusing lower-level failure. This closes two
named-but-unbuilt gaps from MASTER_PROMPT's own Phase 0 file tree; see
``KNOWN_GAPS_AND_ISSUES.md`` for the four other listed ``bin/*.py``
scripts that remain deliberately unbuilt (none wrap an existing
standalone capability).

Unreleased -- Vehicle & pedestrian placement
-----------------------------------------------

Added :mod:`src.procedural.actor_placement` (``ActorPlacementGenerator``):
places vehicles and pedestrians at :mod:`src.procedural.traffic_network`'s
own spawn zones, sampling vehicle type from ``config.vehicle_mix`` and
deriving each actor's heading from its spawn edge's direction of travel.
``BoundingBox3D`` gained ``heading_rad`` (oriented boxes, not just
axis-aligned) and ``category_id`` (:mod:`src.ground_truth.categories`);
``MeshFactory`` gained ``build_vehicle_mesh``/``build_pedestrian_mesh``;
``coco_exporter`` now exports every category (building, sedan, suv,
truck, bus, pedestrian), not just "building"; ``sanity_checker`` gained
``check_vehicle_class_distribution`` (QOL_RESEARCH_CHECKLIST.md Section
H.2's own example check, now directly implemented rather than substituted
with a building-height analogue). This closes the "no vehicle/pedestrian
placement" gap called out below and in ``KNOWN_GAPS_AND_ISSUES.md``.

v0.1.0 -- Phases 0-7 complete
--------------------------------

All 8 phases of ``MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md``'s
roadmap through Phase 7 are implemented, tested, and verified end-to-end:
seed → road network → lanes → buildings → traffic → meshes → validation
→ camera projection → ground truth → COCO export, with parallel and
resumable generation on top. See :doc:`architecture` for what each layer
actually does and what's deliberately not implemented.

This is the first tagged release; there is no prior version to diff
against.

By phase
^^^^^^^^^

**Phase 0 -- Project initialization.** Poetry-managed Python project,
UE5 plugin skeleton, CI (GitHub Actions), scenario/sensor config
templates.

**Phase 1 -- Road network generation.** Planar straight-line graph via
perturbed-grid + Delaunay triangulation. Fixed three real bugs found
while building it: the master prompt's own seed range (``RandomState``
caps at ``2**32-1``, its own tests require ``2**63-1``), a dataclass
``__eq__`` crash on ``numpy.ndarray`` fields, and an intersection
misclassification bug (node degree is always even, since every road is a
bidirectional edge pair -- the master prompt's own ``degree == 3``
T-junction check is unreachable as written).

**Phase 2 -- Lane topology & building placement.** Per-lane boundary
geometry; building placement via Delaunay-triangle city blocks. Found
and fixed a real performance bug (building placement took >60s before a
fix, 0.52s after) and two compounding road-setback correctness bugs
during the same investigation.

**Phase 3 -- Traffic network & procedural meshes.** Traffic light/stop
sign assignment, spawn zones, Dijkstra navigation graph; road/building
mesh geometry (Python-side, since the master prompt contradicts itself
on whether this is Python or C++/UE5 -- resolved in favor of the
testable side). Fixed a real bug: forward/reverse road edges had
independently-sampled, frequently mismatched lane counts since Phase 1.

**Phase 4 -- UE5 integration & scene loading.** ``ScenarioValidator``
(bounds + finite-geometry checks) and a genuine JSON-RPC-over-WebSocket
client, tested against a local mock server. ``ScenarioValidator``'s
first real test caught a bug that had existed silently since Phase 1:
road network nodes could land outside the caller's declared bounds.

**Phase 5 -- Sensor simulation & ground truth.** Camera projection,
LiDAR ray-casting, depth maps, 3D/2D bounding boxes, instance
segmentation -- all real geometry, fully tested without any rendering
engine.

**Phase 6 -- Export & validation.** COCO JSON export (schema-validated
against the real ``pycocotools`` parser), metadata aggregation, dataset
sanity checks, and the orchestration entry point tying every prior phase
into one real pipeline. NuScenes export and sim2real analysis
deliberately not implemented (see :doc:`architecture`).

**Phase 7 -- Distributed generation & optimization.** Ray-based parallel
generation (verified byte-identical output vs. sequential) and
checkpointed/resumable generation (verified a crash-then-resume run only
regenerates missing scenarios). Found and fixed an annotation-ID
collision bug in the resumable path.

Known limitations
^^^^^^^^^^^^^^^^^^

See :doc:`architecture`'s "deliberately not implemented" section and
``KNOWN_GAPS_AND_ISSUES.md`` for the complete list. Highlights: the
``unreal_plugin/`` C++ has never been compiled (no UE5.4 install in any
environment this was built in); ray-casting/rasterization have no
spatial acceleration structure.
