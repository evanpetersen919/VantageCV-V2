Release Notes
==============

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
