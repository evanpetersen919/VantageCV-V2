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
       E --> EA[ActorPlacementGenerator]
       C --> F[MeshFactory]
       D --> F
       EA --> F
       B --> G[ScenarioValidator]
       C --> G
       D --> G
       F --> G
       EA --> G
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
   networks (planar straight-line graph via perturbed-grid + Delaunay
   triangulation), per-lane boundary geometry, building placement
   (Delaunay triangles as an approximate city-block partition), traffic
   control assignment, vehicle/pedestrian placement at
   :mod:`src.procedural.traffic_network`'s own spawn zones
   (:mod:`src.procedural.actor_placement` -- oriented, heading-aware
   boxes sampled from ``config.vehicle_mix``), and mesh generation (road
   surface strips, building/vehicle/pedestrian boxes).

   Determinism: every generator owns an isolated
   ``numpy.random.Generator(numpy.random.PCG64(seed))`` -- not the legacy
   ``RandomState`` the master prompt's own reference code uses, which
   only accepts seeds up to ``2**32-1`` and fails the master prompt's own
   test requirement of a ``2**63-1`` seed (see
   :mod:`src.procedural.road_network`'s module docstring for the full
   story). No generator touches global random state.

**Sensors & ground truth** (``src/sensors/``, ``src/ground_truth/``, Phase 5)
   Pure geometry/math, genuinely tested without any rendering engine:
   pinhole camera projection, LiDAR ray-casting (Moeller-Trumbore
   ray-triangle intersection against the same mesh buffers
   :mod:`src.procedural.mesh_factory` produces), depth map rendering,
   and 3D/2D bounding box + instance segmentation extraction (segmentation
   exploits that a building is a convex box: its silhouette is exactly
   the convex hull of its projected corners).

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
   disk rather than regenerated.

**UE5 integration** (``unreal_plugin/``, ``src/ue5/``, Phase 4)
   :mod:`src.ue5.backend` is a genuine, tested JSON-RPC-over-WebSocket
   client (tested against a local mock server). The C++ side
   (``unreal_plugin/SyntheticDataGen/``) is a structurally-standard but
   **never compiled** UE5 plugin skeleton -- no UE5.4 install exists in
   any environment this project has been built in. Treat everything
   under ``unreal_plugin/`` as unverified until someone with UE5.4
   actually opens and builds it.

What is deliberately not implemented
--------------------------------------

- **NuScenes export and sim2real distribution analysis** (Phase 6):
  NuScenes' schema is built around temporal sequences of dynamic
  objects, which this pipeline doesn't generate; sim2real analysis needs
  real reference data, which doesn't exist in this project.
- **A spatial acceleration structure** for ray-casting/rasterization
  (LiDAR, depth maps, segmentation): all are correct but brute-force,
  fine at the scale this pipeline is tested at, not benchmarked at
  real-dataset scale.
- **GPU-count scaling tests** (Phase 7): this pipeline's workload is
  pure CPU/NumPy; nothing in it uses a GPU, so GPU-count scaling isn't a
  meaningful axis regardless of environment.

See ``KNOWN_GAPS_AND_ISSUES.md`` for the complete, continuously-updated
list, including every bug found and fixed along the way and the
reasoning behind every scope decision above.
