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

1. **Building placement's per-candidate setback check**
   (:mod:`src.procedural.building_placement`). Already fixed once during
   Phase 2 development -- an earlier version checked every placement
   candidate against *every* road segment in the whole scenario and took
   >10s per scenario; fixed by spatially pre-filtering with a cheap
   padded-AABB test before the exact (sqrt-based) distance check, and by
   capping wasted attempts once a block is effectively full. Confirmed
   fix: 769 buildings generated in 0.52s post-fix vs. >60s (killed)
   before, on an identical scenario. If you're extending this module,
   don't remove that pre-filter.

2. **Ray's per-task overhead**
   (:mod:`src.orchestration.distributed_runner`). Each scenario currently
   re-serializes its full ``ScenarioTypeConfig`` and result set per task;
   for scenarios this cheap, that overhead eats into the theoretical
   parallel speedup. Now benchmarked at real scale -- see "Ray
   parallelism: when it's worth it" below; it's real, but sub-linear.

What's already been fixed
----------------------------

- **Building placement O(total_buildings²) → O(buildings_per_block²)**
  overlap checking (Phase 2). See item 1 above.
- **LiDAR ray-casting and depth-map rendering**
  (:mod:`src.sensors.lidar_model`, :mod:`src.ground_truth.depth_map`)
  used to be brute-force O(rays × triangles) / O(pixels × triangles),
  with every ray tested against every triangle of every mesh. Replaced
  by ``TriangleGrid``, an exact (not approximate) uniform-grid spatial
  index (Amanatides & Woo 1987 traversal) that culls triangles outside
  a ray's path; verified against the original brute-force
  ``closest_hit_distance`` across hundreds of randomized trials before
  being trusted. See ``KNOWN_GAPS_AND_ISSUES.md`` for the real
  cross-platform (Windows vs. Linux ``libm``) bug this surfaced and
  fixed along the way.
- **Instance segmentation rasterization**
  (:mod:`src.ground_truth.segmentation`) used to run one full-image
  ``matplotlib.path.Path.contains_points`` pass per object regardless
  of how small that object was in the frame. ``_paint_silhouette`` now
  clips each object's rasterization to its own bounding box first;
  verified exact (0 mismatches vs. brute force across 100 randomized
  polygons) and ~715x faster for a small object in a large frame.
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
placement), real wall-clock benchmarking (Ray parallelism, resumable
generation), or algorithmic reasoning verified against brute-force
correctness (the LiDAR/segmentation spatial-index work under "What's
already been fixed"), not a profiler flagging the actual hot path at
scale. Before optimizing further, profile first -- don't assume the
items above are still the dominant costs once real vehicle/pedestrian
placement and higher sensor resolutions are added (see
:doc:`architecture`'s "deliberately not implemented" section).

Ray parallelism: when it's worth it
---------------------------------------

:func:`src.orchestration.distributed_runner.generate_dataset_distributed`
is verified *correct* (byte-identical output to sequential generation,
both in the test suite and again below at real scale) and has now been
benchmarked for *efficiency* on a real 32-core machine, not just
correctness-tested at 2-3 scenarios across 2 workers.

Real measured wall-clock speedup vs. sequential ``generate_dataset``,
same config/bounds, confirmed byte-identical output at every point:

============  =========  =========
Scenarios     4 workers  8 workers
============  =========  =========
N=12          1.29x      --
N=40          1.82x      2.14x
============  =========  =========

The speedup is real but consistently sub-linear (never close to 4x/8x),
even though the machine had far more idle cores available and wasn't
CPU-starved. The exact root cause hasn't been isolated (per-task
serialization of ``ScenarioTypeConfig`` and results is the leading
suspect -- see item 2 above -- but this hasn't been confirmed with a
profiler against the Ray path specifically); see
``KNOWN_GAPS_AND_ISSUES.md`` for the full writeup. Practical takeaway:
Ray parallelism is worth using for large generation jobs (the 2x+ wins
at N=40 are real time saved), but don't assume near-linear scaling when
sizing worker counts -- benchmark your own workload rather than
extrapolating from worker count alone.

Resumable generation
------------------------

:func:`src.orchestration.resume_handler.generate_dataset_resumable` has
been verified against a real simulated crash, not just the existing
mocked call-count unit test: a full run was started, "crashed" partway
through (killed after 4 of 8 scenarios, leaving ``checkpoint.json`` and
partial output on disk), then resumed with the same arguments for the
full scenario count. The resumed run only regenerated the missing
scenarios (measured wall-clock time for the resumed call was consistent
with 4 scenarios' worth of work, not 8), and the final
``annotations.json`` was byte-identical to an uninterrupted run over
the same scenarios. See ``KNOWN_GAPS_AND_ISSUES.md`` for the exact
timings.

Live rendering time (measured)
--------------------------------

Everything above is about the Python generator. Rendering frames in the live UE5 game is far slower
and dominates a dataset's cost. Measured from the per-scenario timings of three 800-scenario runs
(2,037, 2,051 and 2,037 frames; 24,800 to 26,000 s each, 12.2 s per frame, 31 to 32 s per scenario,
p10 25 s and p90 36 to 42 s):

* **Fixed waits, about 57% of the run, GPU idle:** a 10 s sleep after every scenario load
  (``load_seconds`` in ``src/orchestration/live_render.py``, about 32% of the run), a 3 s sleep
  after every camera move (``settle_seconds``, about 25%), and file polling for each screenshot
  (about 6%, estimated).
* **About 38% is not attributed** (inferred, not profiled): the engine's screenshot latency and
  PNG encoding, a copy and image decode to read the size, the analytic ground truth
  (``render_frame``) and the QA overlay written for every frame.
* The loop is fully serial: Python ground truth and QA writing block the next engine call.

Ideas that were costed but not built (``EXPERIMENT_LOG.md``'s throughput discussion): replace the
two sleeps with a readiness signal from the plugin (about 1.6x to 1.9x; check by pixel-diffing the
old and new capture, since the sleeps may hide streaming, exposure or temporal-AA settling), overlap
the Python work with the engine and make the QA overlay optional (no change to the images), and run
two or three game instances on one GPU with per-instance ports and screenshot paths (the
listening port is a constant in ``SyntheticDataGenRpcSubsystem.h``). A 510-image screening batch
takes about 1.7 h today.
