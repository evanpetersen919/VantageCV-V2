Release Notes
==============

Unreleased -- Real end-to-end UE5 integration: a generated scenario rendered in a live editor
---------------------------------------------------------------------------------------------------

Closed the loop on the WebSocket JSON-RPC bridge from the previous
entry: implemented real mesh-section dispatch in
``AProceduralScenarioLoader::LoadProceduralScenario`` (parses the
payload's ``"meshes"`` array -- vertices/triangles/uvs/material,
matching :mod:`src.procedural.mesh_factory`'s ``Mesh`` dataclass field
for field -- and calls ``UScenarioMeshBuilder::BuildMeshSection`` once
per mesh), replacing what was previously a stub that only validated
JSON.

Verified with a real, full-scale end-to-end test, not a toy payload:
generated one real ``urban_dense`` scenario via this repo's own
:func:`src.orchestration.dataset_generator.generate_scenario` (840
meshes), sent it over the real WebSocket bridge to a live UE 5.4.4
editor with Play-In-Editor running, confirmed via the editor's own log
that all 840 mesh sections built successfully, and then confirmed
**visually** in the PIE viewport that real geometry was actually
there. This is the first time anything this pipeline has generated has
been seen rendered by an actual engine, rather than only plotted via
matplotlib or asserted correct by a unit test -- the culmination of
this session's UE5 dogfooding work.

Unreleased -- Real UE5.4 integration: plugin compiles, WebSocket JSON-RPC bridge works
---------------------------------------------------------------------------------------------------

Set up a real UE 5.4.4 + Visual Studio 2022 environment and, for the
first time in this project's history, actually compiled and ran
``unreal_plugin/SyntheticDataGen/`` against a live editor rather than
treating it as an unverified skeleton. Fixed two real compile bugs
found this way (an ``FColor``/``FLinearColor`` mismatch in
``ScenarioMeshBuilder``'s ``CreateMeshSection`` call; a missing
``ProceduralMeshComponent`` plugin dependency declaration).

Built the piece that made :mod:`src.ue5.backend` untestable against
anything real: ``USyntheticDataGenRpcSubsystem``, a
``UGameInstanceSubsystem`` hosting a WebSocket JSON-RPC server (via the
engine's own ``WebSocketNetworking`` plugin) that answers ``Ping`` and
``LoadProceduralScenario``. Verified with a real, non-mocked round
trip: ``UE5Backend("ws://localhost:8765").ping()`` run from this repo
against a live Play-In-Editor session, succeeding repeatedly. Getting a
clean compile took three wrong turns worth remembering (see
``KNOWN_GAPS_AND_ISSUES.md``'s "[RESOLVED] WebSocket JSON-RPC bridge"
entry for the full detail) -- all stemming from a ``UCLASS`` holding a
``TUniquePtr`` member of a type only forward-declared in its header;
resolved by using a raw pointer with manual cleanup instead, which
sidesteps the whole category of problem (implicit destructors, and a
separate UnrealHeaderTool-generated hot-reload constructor, both
independently needing the complete type).

Also found a real, still-open latency oddity: the same ~2-second
round-trip variance previously seen only against the *mock* server
(suspected antivirus interference on new local socket connections) now
also appears against the *real* UE5 server, at nearly the same value --
a second independent data point supporting that theory. A related
quirk (``localhost`` connects fine; explicit ``127.0.0.1``/``::1`` are
both refused) remains unexplained.

Unreleased -- Dogfooding pass: Ray parallelism benchmarked, resumable generation crash-tested
---------------------------------------------------------------------------------------------------

Second dogfooding round, this time targeting Phase 7's parallel/resumable
generation paths, which had only ever been correctness-tested at tiny
scale (2-3 scenarios, 2 workers). Ran
:func:`src.orchestration.distributed_runner.generate_dataset_distributed`
against real ``generate_dataset`` baselines on a real 32-core machine:
1.29x speedup at N=12 (4 workers), 1.82x at N=40 (4 workers), 2.14x at
N=40 (8 workers) -- consistently sub-linear even with idle cores
available, root cause not yet isolated (see ``KNOWN_GAPS_AND_ISSUES.md``).
Output confirmed byte-identical to sequential generation at every point
measured, not just in the existing small-scale test.

Also simulated a real crash-and-resume of
:func:`src.orchestration.resume_handler.generate_dataset_resumable`:
started a full run, killed it after 4 of 8 scenarios (leaving
``checkpoint.json`` and partial output on disk), then resumed with the
same arguments for the full count. Confirmed the resumed run only
regenerated the missing scenarios (by wall-clock time) and that the
final ``annotations.json`` was byte-identical to an uninterrupted run --
going beyond the existing mocked call-count unit test. Updated
:doc:`performance_tuning` with the real numbers from both experiments,
and to remove two now-stale entries (LiDAR/depth-map and segmentation
rasterization were listed there as still-unaccelerated brute-force
costs, but had already been fixed by ``TriangleGrid``/
``_paint_silhouette`` in earlier work this session -- that doc just
never got updated when those landed).

Unreleased -- Dogfooding pass: real camera framing bug found and fixed
--------------------------------------------------------------------------

Generated an actual 50-scenario dataset via ``bin/generate_dataset.py``
and inspected it directly (COCO schema via ``pycocotools``, category/
vehicle-mix distributions, and -- since no rendering engine exists to
eyeball real frames -- a top-down 2D plot of one scenario compared
side-by-side against ``default_overview_camera``'s own projected 2D
annotations). Found and fixed a real, visually obvious framing bug: the
default camera's offset/height ratios left most of the image empty
(~55% width utilization); retuned to fill the frame far better, with a
new regression test guarding against it recurring. Also documented,
explicitly and where a user would actually see it (``user_guide.rst``'s
CLI section), that this pipeline never produces actual image files --
``annotations.json``'s own ``file_name`` field references a ``.png``
that is never written, since no rendering engine exists to produce one.
See ``KNOWN_GAPS_AND_ISSUES.md`` for both findings in full.

Unreleased -- Gable roofs for residential buildings
---------------------------------------------------------

Added ``_gable_roof_mesh_parts`` to ``mesh_factory.py``: RESIDENTIAL
buildings now get a real gable (pitched) roof (ridge along the
footprint's longer axis, peak ``RESIDENTIAL_ROOF_HEIGHT_METERS`` above
the flat-roof-equivalent eave height) instead of the flat cap every
building previously got regardless of type. MIXED_USE/COMMERCIAL
buildings are unaffected (still the original 8-vertex/12-triangle
flat-roofed box) -- real low/mid-rise commercial buildings are
overwhelmingly flat-roofed, so this is a deliberate type-driven choice.
10 vertices, 16 true triangles (not fan-triangulated quads, since the 2
gable-end faces are triangular by construction); every triangle's
outward-facing winding verified directly for both ridge orientations.

Unreleased -- Configurable road setback
--------------------------------------------

Added ``ScenarioTypeConfig.road_setback_meters`` (``>= 0``, default
``2.0``), replacing ``building_placement.py``'s fixed
``ROAD_SETBACK_METERS`` module constant -- ``BuildingPlacementGenerator``
now reads it from config instead. ``config_loader.py`` maps it from a
template's optional ``buildings.road_setback_meters`` YAML key;
``urban_dense.yaml``/``urban_sparse.yaml`` now set genuinely different
values (``2.0``/``4.0``), not just a passthrough field that's never
varied. The default matches the old constant exactly, so every
pre-existing caller/template kept working unchanged.

Unreleased -- Building types and materials
----------------------------------------------

Added ``BuildingType`` (RESIDENTIAL/MIXED_USE/COMMERCIAL -- a taxonomy
of this codebase's own invention, since MASTER_PROMPT specifies none)
and per-type material assignment to ``building_placement.py``, closing
a gap deliberately deferred until the mesh factory existed to consume
it. Each building's type is derived from where its own sampled height
falls *relative to* ``config.building_heights``'s own range (bottom
third residential, middle third mixed-use, top third commercial) rather
than a fixed threshold, since that range varies enormously across
scenario templates. ``mesh_factory.py``'s ``build_building_mesh`` now
uses ``building.material`` instead of a hardcoded ``"concrete"``.
``Building.building_type``/``material`` both default to the old
hardcoded behavior, so every pre-existing caller/test kept working
unchanged.

Unreleased -- Accelerated segmentation mask rasterization
----------------------------------------------------------------

Each object's point-in-polygon test in ``rasterize_instance_masks`` (via
the new ``_paint_silhouette`` helper) now only runs over its own
projected silhouette's pixel bounding box, clipped to the image, instead
of a full-image pass regardless of the object's actual on-screen size.
An exact optimization, not an approximation -- verified directly against
a brute-force full-image reference across 100 randomized convex polygon
shapes/positions in ``test_segmentation.py``, including silhouettes
partially or fully outside the frame. For a small object in a large
frame this is a two-to-three-order-of-magnitude reduction in points
tested. Closes the sibling gap to the LiDAR/depth-map spatial
acceleration below -- same underlying problem (an O(image size) pass per
object), a different (non-ray-casting) algorithm.

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
