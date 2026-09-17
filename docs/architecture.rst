Architecture
============

This describes the system as actually built (Phases 0-7 complete), not
the aspirational version in
``MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md`` Section 1 -- where
the two disagree, this page and the code win; the master prompt is the
original specification, not always an accurate description of what
exists. See :doc:`release_notes` for what shipped in each phase and
``KNOWN_GAPS_AND_ISSUES.md`` (repo root) for every deliberate scope
decision and every bug found along the way.

Pipeline overview
------------------

.. mermaid::

   flowchart TD
       A[seed + ScenarioTypeConfig + bounds] --> B[RoadNetworkGenerator]
       B --> C[LaneTopologyGenerator]
       B --> D[BuildingPlacementGenerator]
       C --> E[TrafficNetworkGenerator]
       D --> E
       C --> EB[LaneConnectivityGenerator]
       E --> EA[ActorPlacementGenerator]
       C --> F[MeshFactory]
       D --> F
       EA --> F
       B --> G[ScenarioValidator]
       C --> G
       D --> G
       F --> G
       EA --> G
       EB --> G
       F --> H[Camera projection]
       D --> H
       EA --> H
       H --> I[bbox_3d / bbox_2d / segmentation / depth_map]
       I --> J[coco_exporter]
       J --> K[annotations.json]

Every box is a real module under ``src/``, wired together end-to-end in
:func:`src.orchestration.dataset_generator.generate_scenario` and
:func:`src.orchestration.dataset_generator.generate_dataset`.

Layers
------

**Procedural generation** (``src/procedural/``, Phases 1-3)
   Deterministic, seed-driven generation of the scenario's geometry: road
   networks (planar straight-line graph, a plain orthogonal grid --
   straight roads, square 90-degree intersections only, by deliberate
   choice; an earlier perturbed-grid + Delaunay-triangulation approach
   produced organic but arbitrary-angle streets whose acute-angle
   intersections had no exact fix for real, measured lane-mesh
   self-overlap in UE5 -- see :mod:`src.procedural.road_network`'s own
   module docstring and ``KNOWN_GAPS_AND_ISSUES.md``), per-lane boundary
   geometry (trimmed short of each intersection, now exact rather than a
   partial mitigation now that every intersection is square), building
   placement (each grid cell is an exact rectangular city block, each
   building kept clear of every road's real lane-pavement width -- not
   just ``config.road_setback_meters`` from the centerline -- and
   assigned a type -- residential/mixed-use/commercial, by relative
   height within ``config.building_heights`` -- and a matching exterior
   material), traffic control assignment, per-lane turn connectivity
   across intersections
   (:mod:`src.procedural.lane_connectivity` -- which lane legally feeds
   which other lane, classified straight/left/right from edge geometry
   and ``RoadEdge.allows_turning_left``/``allows_turning_right``),
   vehicle/pedestrian placement at :mod:`src.procedural.traffic_network`'s
   own spawn zones (:mod:`src.procedural.actor_placement` -- oriented,
   heading-aware boxes sampled from ``config.vehicle_mix``), and mesh
   generation (road surface strips, vehicle/pedestrian boxes, and
   buildings -- a flat-roofed box for MIXED_USE/COMMERCIAL, a real gable
   roof for RESIDENTIAL).

   Determinism: every generator owns an isolated
   ``numpy.random.Generator(numpy.random.PCG64(seed))`` -- not the legacy
   ``RandomState`` the master prompt's own reference code uses, which
   only accepts seeds up to ``2**32-1`` and fails the master prompt's own
   test requirement of a ``2**63-1`` seed (see
   :mod:`src.procedural.road_network`'s module docstring for the full
   story). No generator touches global random state.

**Sensors & ground truth** (``src/sensors/``, ``src/ground_truth/``, Phase 5)
   Pure geometry/math, genuinely tested without any rendering engine:
   pinhole camera projection (optionally with Brown-Conrady lens
   distortion -- ``CameraIntrinsics.distortion_coeffs``, ``None`` by
   default), LiDAR ray-casting (Moeller-Trumbore ray-triangle
   intersection against the same mesh buffers
   :mod:`src.procedural.mesh_factory` produces, accelerated by
   ``TriangleGrid``'s uniform-grid spatial index rather than testing
   every triangle per ray, optionally with Gaussian range noise --
   ``LidarConfig.range_noise_std_m``), depth map rendering (same
   ``TriangleGrid`` acceleration, optionally with Gaussian depth noise --
   ``render_depth_map``'s own ``noise_std_m``), and 3D/2D bounding box +
   instance segmentation extraction (segmentation exploits that a
   building is a convex box: its silhouette is exactly the convex hull
   of its projected corners, and each object's mask is painted only over
   its own projected pixel bounding box rather than the full image).

**Export & validation** (``src/export/``, ``src/validation/``, Phase 6)
   COCO JSON export (schema-validated against the real ``pycocotools``
   parser, not just hand-written checks), scenario metadata (git commit,
   config version, dependency versions), and dataset-wide sanity checks.

**Orchestration** (``src/orchestration/``, Phases 6-7)
   :mod:`src.orchestration.dataset_generator` chains every layer above
   into one pipeline and writes real files to disk.
   :mod:`src.orchestration.distributed_runner` parallelizes scenario
   generation across CPU cores via Ray (local mode -- no cluster or GPU
   involved; see :doc:`performance_tuning`).
   :mod:`src.orchestration.resume_handler` adds checkpointed, resumable
   generation: an interrupted run's completed scenarios are loaded from
   disk rather than regenerated. ``bin/generate_dataset.py`` is a thin
   CLI wrapper over :func:`src.orchestration.dataset_generator.generate_dataset`,
   using :func:`src.utils.config_loader.load_scenario_config` to build a
   ``ScenarioTypeConfig`` from one of ``configs/scenario_templates/``'s
   own YAML files.

**UE5 integration** (``unreal_plugin/``, ``src/ue5/``, Phase 4)
   :func:`src.orchestration.scenario_serializer.serialize_scenario`
   converts a ``ScenarioResult`` into the plain-JSON shape
   ``UE5Backend.load_scenario``/``ProceduralScenarioLoader.cpp`` expect
   -- the real, previously-missing bridge between Python-side generation
   and the UE5-side pipeline described below (earlier real-UE5
   verification ran through an ad hoc scratchpad script; this is that
   logic made real, committed, and tested). ``bin/send_scenario_to_ue5.py``
   is a thin CLI wrapper tying ``generate_scenario`` → ``serialize_scenario``
   → :meth:`src.ue5.backend.UE5Backend.load_scenario` together, replacing
   that scratchpad script.

   The serialized payload carries two top-level arrays: ``"meshes"``
   (roads, and non-hero building/pedestrian box geometry -- raw
   vertex/triangle/UV data) and ``"assets"`` (asset-reference + transform
   entries: ``{"category", "asset_path", "position", "rotation_rad",
   "id"}``, for real City Sample content this project spawns rather than
   builds as a procedural box). As of the City Sample asset integration's
   Phase 1, vehicles are the first ``"assets"`` category populated --
   each ``Vehicle`` samples a real City Sample vehicle Blueprint path
   deterministically (:mod:`src.procedural.city_sample_assets`) instead
   of feeding a box mesh into ``ScenarioResult.meshes``; ground truth is
   unaffected, since bounding boxes are still derived from ``Vehicle``'s
   own placement-time fields, not from mesh geometry. Props and landmark
   buildings are planned to populate their own ``"assets"`` categories in
   later phases of that same effort.

   :mod:`src.ue5.backend` is a genuine, tested JSON-RPC-over-WebSocket
   client -- verified 2026-09-15/16 against a local mock server, a real
   live UE 5.4.4 editor (``Ping``), and a full real scenario
   (``LoadProceduralScenario``). The C++ side
   (``unreal_plugin/SyntheticDataGen/``) now compiles and loads cleanly
   against a real UE 5.4.4 install: ``USyntheticDataGenRpcSubsystem``
   (a ``WebSocketNetworking``-based JSON-RPC server) and
   ``AProceduralScenarioLoader`` (which parses a scenario's ``"meshes"``
   array and dispatches real ``UScenarioMeshBuilder::BuildMeshSection``
   calls) have both been exercised end-to-end: a real 840-mesh
   ``urban_dense`` scenario generated by this repo's own pipeline, sent
   over the real WebSocket bridge to a live Play-In-Editor session,
   produced real geometry that was visually confirmed in the viewport
   -- the first time anything this pipeline generated has been seen
   rendered by an actual engine, not just plotted or asserted correct
   by a test. See ``KNOWN_GAPS_AND_ISSUES.md`` for the real,
   non-obvious C++ compile failures fixed along the way and what's
   still open (traffic-controller initialization and streaming/culling
   aren't implemented; a D3D12 shader-compiler crash on this machine
   needs a ``-d3d11`` launch workaround; the C++ side of Phase 1's
   ``"assets"`` parsing/spawning is not yet implemented).

What is deliberately not implemented
--------------------------------------

- **NuScenes export and sim2real distribution analysis** (Phase 6):
  NuScenes' schema is built around temporal sequences of dynamic
  objects, which this pipeline doesn't generate; sim2real analysis needs
  real reference data, which doesn't exist in this project.
- **GPU-count scaling tests** (Phase 7): this pipeline's workload is
  pure CPU/NumPy; nothing in it uses a GPU, so GPU-count scaling isn't a
  meaningful axis regardless of environment.

See ``KNOWN_GAPS_AND_ISSUES.md`` for the complete, continuously-updated
list, including every bug found and fixed along the way and the
reasoning behind every scope decision above.
