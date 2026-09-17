Release Notes
==============

Unreleased -- Vehicle paint materials fixed: real root cause was a missing content mount, not MassTraffic itself
-------------------------------------------------------------------------------------------------------------------

Vehicle paint materials previously fell back to UE5's default flat
material because City Sample's real ``M_Veh_CarPaint``/``MI_Veh_*``
materials reference a material function
(``MF_UnpackTrafficVehicleInstanceCustomData``) living in Epic's
separate MassTraffic plugin's content mount, which was never migrated.
Heavily re-investigated by decoding the real ``.uasset`` binary
directly rather than guessing: that function's own only dependencies
are standard engine packages and built-in material expression node
types -- nothing from MassTraffic's actual C++ traffic-AI source. It's
pure content that merely lives inside that plugin's folder.

Fixed with a new, minimal, content-only plugin (committed at
``unreal_plugin/Traffic/Traffic.uplugin``, no ``Modules``/``Source`` at
all -- deliberately not a copy of the real MassTraffic plugin) that
registers the same ``/Traffic/`` mount point City Sample's
already-migrated materials already hard-reference, so no material graph
editing was needed. Verified via a real live session: "Missing Material
Function" warnings dropped from many to zero across the whole log, and
real screenshots show genuine distinct paint colors and a real
taillight lens color across 5 different vehicles, not a uniform
fallback. See ``KNOWN_GAPS_AND_ISSUES.md`` for the full investigation
and the manual steps needed to reproduce this on a fresh setup.

Unreleased -- Vehicles fully assembled: wheels, doors, glass, interior, steering wheel
----------------------------------------------------------------------------------------

Vehicles were body-shell-only (``SM_Frame_<name>`` alone -- no wheels,
doors, windows, or interior). Real live testing confirmed every
vehicle's own wheel/door/glass/interior/steering-wheel static meshes
are pre-modeled in their final assembled position already, so spawning
each as a sibling component at the exact same transform as the body
(no offset/socket math needed) produces a correctly assembled vehicle
-- confirmed via a sequence of real screenshots.

``city_sample_assets.py`` gained ``VEHICLE_PART_PATHS``, a real
per-vehicle part catalog (genuinely non-uniform across the 14 vehicles
-- the two dual-rear-axle trucks have 6 wheels, the trailer has 6
wheels and no doors/glass/interior, the bus has 4 wheels and no doors).
``scenario_serializer.py`` now emits a ``"part_paths"`` field per
vehicle asset entry; ``UVehicleActorSpawner`` spawns each part as its
own ``UStaticMeshComponent``. A real, documented near-bug was fixed
along the way: parts must attach with ``KeepRelativeTransform``, not
``KeepWorldTransform``, or every part lands at world origin instead of
on the vehicle.

Verified end-to-end through the real pipeline (``bin/send_scenario_to_ue5.py``,
not hand-crafted test JSON): all 14 vehicles' full assemblies spawn
with 0 skips, confirmed via engine log and a real screenshot. Still
open: vehicle paint materials/textures (a separate, deeper City Sample
plugin-dependency problem -- see ``KNOWN_GAPS_AND_ISSUES.md``).

Unreleased -- Three real bugs found via live dogfooding: invisible vehicles, inconsistent road widths, thin blocks
--------------------------------------------------------------------------------------------------------------------

Found by watching several procedurally generated city layouts cycle live
in a real standalone UE5 session:

1. Vehicles spawned successfully (confirmed by the engine log) but were
   never visible -- ``SpawnActor``'s transform was silently dropped
   because a bare ``AActor`` has no root component at spawn time, so
   every vehicle landed at world origin. Fixed in
   ``UVehicleActorSpawner::SpawnVehicle`` by setting the actor's
   transform explicitly once its real root component exists.
2. Road widths visibly varied scenario-to-scenario -- ``num_lanes`` was
   sampled randomly (2-4) per road, and rendered pavement width is
   ``num_lanes * LANE_WIDTH_METERS``. Pinned to a new
   ``UNIFORM_LANE_COUNT = 2`` constant for this stage of the project;
   road hierarchy/speed limit still vary.
3. Two same-direction roads could end up separated by an unrealistically
   thin sliver of buildings -- ``RoadNetworkGenerator._axis_coords``
   let the final grid interval on an axis be whatever leftover distance
   remained after fitting full-size blocks, which could be far shorter
   than every other block. Fixed by quantizing each axis to a whole
   number of *equal*-width intervals instead, so every block on one
   axis is now the same size.

Also added ``AProceduralScenarioLoader::ClearPreviousScenario``
(destroys prior mesh sections and spawned vehicles before loading a new
scenario), needed once a running session started being reused to cycle
through multiple generated layouts live rather than loading exactly one
scenario per session.

See ``KNOWN_GAPS_AND_ISSUES.md`` for full root-cause detail on each bug.

Unreleased -- Vehicles still invisible after the above fix: two more real bugs found via actual screenshots
-----------------------------------------------------------------------------------------------------------

The vehicle-position fix above was real but not sufficient -- vehicles
were still not visible. Diagnostic logging showed everything looked
correct (matching position, valid non-degenerate mesh bounds,
``visible=1``), which turned out to be actively misleading: two new
permanent RPC debugging methods (``TakeScreenshot``,
``DebugMoveCameraTo``) were built to get real visual ground truth, and
found:

1. The camera was never pointed at the generated content at all -- a
   screenshot showed the current level's own default template geometry.
   The level's default ``PlayerStart`` has no relationship to a
   generated scenario's coordinates. Fixed: ``LoadProceduralScenario``
   now repositions the local player's pawn to overlook the real bounds
   of whatever was just built, mirroring
   ``default_overview_camera()``'s own logic in ``dataset_generator.py``.
2. Even with the camera fixed, vehicles rendered as only a tiny sliver
   of their true geometry -- City Sample's combined skeletal vehicle
   rigs drive a runtime damage-state system that needs an active
   ``AnimBlueprint`` to show the intact body, confirmed by testing
   alternate mesh variants directly against the same position. Fixed:
   ``UVehicleActorSpawner`` now loads each vehicle's static
   ``SM_Frame_<name>`` body-shell mesh instead (no skeleton, no pose
   dependency, renders unconditionally) -- ``city_sample_assets.py``'s
   ``VEHICLE_ASSET_PATHS`` repointed accordingly for all 14 vehicles.
   Real, documented limitation: body shell only, no wheels/doors.

A final overview screenshot confirms multiple real, recognizable
vehicle silhouettes correctly positioned along the generated roads.
See ``KNOWN_GAPS_AND_ISSUES.md`` for the full investigation and the
lesson recorded there: a clean engine log is not evidence of a correct
render.

Unreleased -- City Sample asset integration, Phase 0: real scenario serializer, investigation complete
---------------------------------------------------------------------------------------------------------

First phase of a new, planned multi-phase effort (``feature/city-sample-asset-integration``
branch) to replace today's flat-gray procedural boxes with real assets
from Epic's free City Sample project, while keeping this project's own
procedural placement and ground-truth logic entirely unchanged.

Found and fixed a real gap: no committed code converted a
``ScenarioResult`` into the JSON shape UE5 actually expects -- every
real UE5 verification earlier this session ran through an uncommitted
scratchpad script. Added :func:`src.orchestration.scenario_serializer.serialize_scenario`
(real round-trip tests) and ``bin/send_scenario_to_ue5.py`` (a real,
permanent CLI replacing that scratchpad script, tested against a local
mock WebSocket server covering success/error/timeout paths).

Resolved both open investigation questions with real file-level
evidence from City Sample's installed content, no guessing: vehicles
are genuine Blueprint actors with Chaos physics/skeletal animation, not
simple static meshes; pedestrians have a real standalone
``BP_CrowdCharacter`` Blueprint (6 male + 6 female variants, weight
variants, accessories) suggesting they're spawnable the same way, final
confirmation deferred to Phase 1's manual PIE pass.

Unreleased -- City Sample asset integration, Phase 1: real vehicles spawning and verified live
--------------------------------------------------------------------------------------------------

Follow-up to Phase 0 above. Vehicles no longer feed box geometry into
``ScenarioResult.meshes``: :class:`src.procedural.actor_placement.Vehicle`
gained a deterministically-sampled ``asset_path`` field pointing at a
real City Sample vehicle skeletal mesh (new
:mod:`src.procedural.city_sample_assets` catalog -- 14 non-hero vehicle
models across sedan/suv/truck/bus). Ground truth is unaffected:
bounding boxes still derive from ``Vehicle``'s own placement-time
fields, not from mesh data.
:func:`src.orchestration.scenario_serializer.serialize_scenario`'s
``"assets"`` array (present but empty since Phase 0) now carries one
``category: "vehicle"`` entry per placed vehicle.

The C++ spawn path (``UVehicleActorSpawner``) went through a real
architectural pivot mid-verification: City Sample's own driveable
``BP_veh*_Sandbox`` Blueprints turned out to depend on
``ACitySampleVehicleBase``, native C++ living in CitySample's own game
project (Mass AI traffic control, Enhanced Input, a custom UI system)
rather than portable content -- unusable here and not worth porting for
a frozen-frame scene. Rewritten to spawn a plain actor holding just the
real skeletal mesh instead. Fully verified against a live standalone
UE5 session: a real 112-mesh scenario produced 50 spawned vehicle
actors, 0 skipped. See ``KNOWN_GAPS_AND_ISSUES.md`` for the full story,
including a real ``LoadClass`` object-path bug found and fixed along
the way.

Unreleased -- Road network rearchitected to an orthogonal grid: eliminates lane z-fighting entirely
---------------------------------------------------------------------------------------------------

Follow-up to the lane/building overlap fixes below, which reduced but
explicitly couldn't fully eliminate lane self-overlap at intersections
(a uniform per-node trim can't clear sharp/near-parallel intersection
angles). Rather than build an angle-aware miter, rearchitected
``road_network.py`` from perturbed-grid + Delaunay triangulation to a
plain orthogonal grid -- straight roads, square (90-degree)
intersections only. This makes the existing lane-trim fix
mathematically exact: verified 0 overlapping lane-mesh pairs on the
same real scenario shape used throughout this investigation (down from
3,538 originally, 963 after the trim-only fix).

Real, explicit tradeoff: loses the organic, arbitrary-angle street
variety the old approach produced. Diagonal roads may return later as
an additional connection strategy layered on the grid, not a revival of
the old approach.

Real downstream break, caught and fixed immediately: ``building_placement.py``'s
block identification used to re-triangulate node positions internally
and keep only triangles whose edges all survived -- with no diagonal
edges left anywhere in the road graph, every triangle failed that
check, and 5 existing tests immediately caught zero buildings being
placed. Fixed by replacing the triangle *approximation* with exact
rectangular grid-cell block identification -- genuinely more correct
than before, since real city blocks in a grid city are rectangles, not
triangles. Full test suite (441 tests) and lint clean throughout.

Unreleased -- Fixed two real geometry bugs found by actually looking at rendered output
---------------------------------------------------------------------------------------------------

Found via visually inspecting a real scenario rendered in UE5 (not any
prior unit test -- every existing check compared against road
centerlines or fixed distances, never the real rendered lane geometry):
roads looked staticky/noisy, and buildings visibly clipped through the
road surface.

**Lane self-overlap at intersections**: ``lane_topology.py`` offset
each edge's full, untrimmed centerline into lanes, so every edge
meeting at a shared node extended all the way to that point with no
clipping. A real generated scenario had 3,538 overlapping lane-mesh
pairs covering ~38% of its total ground area -- real z-fighting, not a
rendering bug. Fixed by trimming each lane short of both endpoint nodes
by the widest connecting road's own lane half-width
(``LaneTopologyGenerator._compute_node_clearance``), cutting overlap by
72% (pair count) / 43% (area). Not fully eliminated -- sharp/near-
parallel intersection angles need a real angle-aware miter, out of
scope for this pass; see ``KNOWN_GAPS_AND_ISSUES.md``.

**Buildings standing inside road pavement**: ``building_placement.py``
enforced only a small fixed setback from the road *centerline*,
ignoring that a road's real half-width from centerline is
``num_lanes * LANE_WIDTH_METERS`` (up to 14m for a 4-lane edge). 194 of
283 buildings (~69%) on a real scenario overlapped actual lane
geometry. Fixed by adding each edge's own lane half-width to the
setback enforced against it -- verified fully resolved (0 overlapping
buildings) via a new regression test that checks against real,
Shapely-unioned mesh geometry rather than reimplementing the buggy
formula. Building count per scenario drops accordingly (fewer buildings
fit once setback reflects real road width) -- expected, not a
regression.

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
