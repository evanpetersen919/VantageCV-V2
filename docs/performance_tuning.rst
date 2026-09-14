Performance Tuning Guide
==========================

Implements MASTER_PROMPT Section 3.9's "Performance tuning guide"
bullet. Every claim below is backed by an actual finding logged in
``KNOWN_GAPS_AND_ISSUES.md`` during this project's own development, not
generic advice -- follow the links there for the full reasoning and any
test that demonstrates it.

Where the real cost is
------------------------

Profiled indirectly across Phases 1-7 (via test timing, not a dedicated
profiler run -- see the "Not yet done" section below): the expensive
parts of this pipeline, in roughly descending order, are:

1. **LiDAR ray-casting and depth-map rendering**
   (:mod:`src.sensors.lidar_model`, :mod:`src.ground_truth.depth_map`).
   Both are brute-force O(rays × triangles) / O(pixels × triangles) --
   every ray is tested against every triangle of every mesh, with no
   spatial index (BVH/octree/grid) to cull irrelevant geometry. Fine at
   the small scale this pipeline's own tests run at; a real sensor
   config (64-channel LiDAR at ~2000 azimuth samples, or a 1920×1080
   depth map) against a realistic scene would be far too slow.
   **If you need this at real scale**: add a spatial index over each
   mesh's triangles before ray-casting against it.

2. **Instance segmentation rasterization**
   (:mod:`src.ground_truth.segmentation`). One full-image
   ``matplotlib.path.Path.contains_points`` pass per object (vectorized
   across pixels, not across objects). Scales with object count ×
   image resolution.

3. **Building placement's per-candidate setback check**
   (:mod:`src.procedural.building_placement`). Already fixed once during
   Phase 2 development -- an earlier version checked every placement
   candidate against *every* road segment in the whole scenario and took
   >10s per scenario; fixed by spatially pre-filtering with a cheap
   padded-AABB test before the exact (sqrt-based) distance check, and by
   capping wasted attempts once a block is effectively full. Confirmed
   fix: 769 buildings generated in 0.52s post-fix vs. >60s (killed)
   before, on an identical scenario. If you're extending this module,
   don't remove that pre-filter.

4. **Ray's per-task overhead**
   (:mod:`src.orchestration.distributed_runner`). Each scenario currently
   re-serializes its full ``ScenarioTypeConfig`` and result set per task;
   for scenarios this cheap, that overhead could dominate. Not
   benchmarked at real scale -- see below.

What's already been fixed
----------------------------

- **Building placement O(total_buildings²) → O(buildings_per_block²)**
  overlap checking (Phase 2). See item 3 above.
- **`_find_or_create_node`'s O(N) linear scan** in
  :mod:`src.procedural.road_network` is documented as an accepted
  tradeoff at hundreds-of-nodes scale; switch to a ``scipy.spatial.KDTree``
  if profiling ever shows it's the bottleneck at larger scenario sizes.
- **Ray's test-suite startup overhead**: adding ``ray`` measurably slowed
  the full test suite (roughly 50s → 80s) even though few tests use it.
  Not fixed (it's dev-only cost), but if it grows further, consolidate
  Ray-dependent tests to share one ``ray.init()`` via a session-scoped
  fixture rather than each test managing its own.

Not yet done
--------------

No dedicated profiling run (``py-spy``, ``memory-profiler``,
``line-profiler`` -- all part of ``MASTER_PROMPT``'s tech stack, Section
2.2) has actually been performed against this pipeline at any
realistic dataset scale (hundreds or thousands of scenarios). Everything
above comes from either a specific bug investigation (building
placement) or general reasoning about algorithmic complexity (LiDAR,
segmentation), not a profiler flagging the actual hot path at scale.
Before optimizing further, profile first -- don't assume the items above
are still the dominant costs once real vehicle/pedestrian placement
and higher sensor resolutions are added (see :doc:`architecture`'s
"deliberately not implemented" section).

Ray parallelism: when it's worth it
---------------------------------------

:func:`src.orchestration.distributed_runner.generate_dataset_distributed`
is verified *correct* (byte-identical output to sequential generation)
but not benchmarked for *efficiency* at any scale beyond 2-3 scenarios
across 2 workers in tests. Don't assume it's a net win for cheap
scenarios without measuring -- Ray's per-task submission/serialization
overhead is real and could exceed a scenario's own generation cost for
small ``bounds``/sparse configs. Benchmark actual wall-clock scaling
across worker counts on your real workload before committing to it in a
production generation job.
