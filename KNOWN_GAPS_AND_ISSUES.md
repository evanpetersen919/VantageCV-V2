# Known Gaps, Risks & Open Issues

Living log of everything deferred, unverified, or risky in this implementation,
so nothing gets silently lost between sessions/phases. Update this file whenever
a gap is discovered, deferred, or closed. Never delete a closed entry — mark it
`RESOLVED` with the phase/commit that fixed it.

Severity: **BLOCKER** (must fix before shipping) / **RISK** (works but fragile,
should fix before relying on it) / **DEFERRED** (intentionally postponed to a
later phase, tracked so it isn't forgotten).

---

## Open

### [RESOLVED] Scenario config YAML templates were reference-only, never actually loaded
Was: no code anywhere loaded `configs/scenario_templates/*.yaml` at
runtime; every `ScenarioTypeConfig` used in tests/examples/the user guide
was constructed directly in Python.

Resolved by `src/utils/config_loader.py`'s `load_scenario_config`: maps a
template's nested YAML (`road_network:`/`buildings:`/`traffic:` sections)
onto `ScenarioTypeConfig`'s flat constructor fields. Only two of the five
templates are actually loadable this way, though: `urban_dense.yaml` and
`urban_sparse.yaml` share `ScenarioTypeConfig`'s schema because
`RoadNetworkGenerator` implements exactly one generation strategy
(perturbed-grid + Delaunay) regardless of `scenario_type` -- it never
branches on it. `highway.yaml`, `parking_lot.yaml`, and `roundabout.yaml`
describe entirely different, never-implemented generation strategies (see
the Highway `BLOCKER-for-later` entry and the "No parking spawn zones"
entry below) and don't even share `ScenarioTypeConfig`'s field names.
Loading one of those three raises `NotImplementedError` with a message
explaining why, rather than a confusing `KeyError`/`pydantic.ValidationError`
or a silently-wrong config. This is a deliberate, honest scope boundary,
not a partial implementation to revisit -- the fix for those three
templates is implementing their own road-generation strategies (separate,
larger pieces of work each), not extending this loader.

### [RESOLVED] No CLI entry points (`bin/generate_dataset.py` etc.)
Was: every capability this pipeline has was only reachable by importing
the Python API directly, not via a command-line tool.

Resolved by `bin/generate_dataset.py`: an argparse wrapper around
`src.orchestration.dataset_generator.generate_dataset`, using the
`config_loader.py` entry above for its `--config` flag. Handles the two
sys.path gotchas real `bin/` scripts hit in a `src`-layout project: it
inserts the repo root onto `sys.path` before importing `src.*` (running a
script directly puts the script's own directory on `sys.path`, not the
repo root or cwd), and it catches `FileNotFoundError`/`NotImplementedError`/
`ValueError` around config loading and generation to print a clean
one-line message on stderr and exit 1, rather than a raw traceback for
every-day failure modes (bad config path, unsupported scenario type,
`ScenarioValidator` failure). `scripts/run_linter.sh` and
`lint_and_test.yml` both extended to run pylint/mypy against `bin/` too,
not just black/isort as before -- it's real code now.

The other four `bin/*.py` scripts MASTER_PROMPT's Phase 0 file tree lists
(`validate_dataset.py`, `profile_performance.py`, `visualize_scenarios.py`,
`compare_sim2real.py`) still don't exist -- none of them wrap an existing
standalone capability this codebase has (there's no sim2real comparison
logic to expose a CLI for, for instance; see the Sim2real entry above).
Building them now would mean inventing functionality, not exposing
something real, so they're left deferred rather than stubbed out.

A dedicated `documentation.yml` CI workflow (also in MASTER_PROMPT's file
tree) was deliberately not built: `tests/integration/test_docs_build.py`
already runs both the HTML and doctest Sphinx builds as part of the
existing `lint_and_test.yml` `test` job, so a separate workflow would
duplicate that coverage without adding any -- the only thing it could add
(publishing built HTML docs somewhere, e.g. GitHub Pages) wasn't asked
for and needs a deliberate hosting decision, not just a workflow file.

`config_loader.py`'s `import yaml` needed a `mypy --strict` override
(`pyproject.toml`'s `[[tool.mypy.overrides]] module = "yaml.*"`, same
pattern as the pre-existing scipy override): `pyyaml` 6.0.1 ships no
`py.typed` marker, and a real `types-PyYAML` stub package exists but
adding it as a dependency would need regenerating `poetry.lock` via
`poetry lock`, which isn't possible in every environment this project is
built in (see the "Poetry install/lint/test flow" entry below). Revisit
if/when a real Poetry install is confirmed available.

### [DEFERRED] No real multi-node/multi-GPU scaling test
MASTER_PROMPT Section 3.8 lists "Scaling tests (2GPU, 4GPU, 8GPU)" and
"Scaling efficiency" as a test bullet. Neither is implemented: this
environment has no GPUs and no multi-node cluster, and (more
fundamentally) this pipeline's actual workload is pure CPU/NumPy
geometry generation -- nothing in Phases 1-6 touches a GPU, so GPU-count
scaling isn't a meaningful axis for this codebase regardless of
environment. What's implemented instead is genuine CPU-core parallelism
via Ray's local scheduler (`distributed_runner.py`), verified for
correctness (output identical to sequential) but not benchmarked for
efficiency at any real scale -- `tests/integration/test_distributed_runner.py`
only checks 2-3 scenarios across 2 workers, nowhere near enough to say
anything meaningful about scaling efficiency even on CPU cores.
**Action**: if real distributed generation at dataset scale (thousands of
scenarios) is attempted, benchmark actual wall-clock scaling across
worker counts before assuming Ray parallelism is paying off -- per-task
overhead (each scenario currently re-imports/re-serializes its config)
could dominate for cheap scenarios.

### [RISK] `pkg_resources` (needed by Ray, via the pinned `setuptools<81`) is slated for removal by setuptools upstream
The fix above pins `setuptools<81` specifically to keep `pkg_resources`
importable, because `ray` 2.9.3's `ray/_private/pydantic_compat.py` does
`from pkg_resources import packaging` unconditionally whenever a remote
task is first submitted. `pkg_resources` itself now warns on import:
"slated for removal as early as 2025-11-30." When that happens, this
pin will stop being satisfiable (or satisfiable only with an
increasingly ancient setuptools), and every `ray.remote(...).remote()`
call in this codebase will break again the same way.
**Action**: watch for a `ray` release that no longer imports
`pkg_resources` (newer Ray versions past 2.9.3 likely already fixed
this internally) and upgrade `ray` + drop the `setuptools<81` pin
together, rather than pinning setuptools indefinitely.

### [RISK] Ray adds meaningful test-suite startup overhead
Adding `ray` as a dependency increased the full test suite's wall-clock
time noticeably (roughly 50s to 80s) even though only a handful of tests
actually use it -- `ray.init()`'s worker-process startup cost is paid at
least once per test session. Not a correctness issue, but worth knowing
if test suite speed becomes a concern; consolidating Ray-dependent tests
to share one `ray.init()` call (e.g. via a session-scoped fixture) would
likely help if this grows further.

### [DEFERRED] NuScenes format conversion not implemented
MASTER_PROMPT Section 3.7 lists "NuScenes format conversion" as a Phase 6
bullet. Not implemented. NuScenes' schema (scene, sample, sample_data,
ego_pose, calibrated_sensor, category, instance, sample_annotation
tables, cross-referenced by token) is fundamentally built around
*temporal sequences of ego vehicle poses observing dynamic objects*
(vehicles, pedestrians, cyclists) -- this codebase generates dynamic
objects now (`actor_placement.py`, below) but still no multi-frame
temporal sequences (every scenario is a single independent frame). A
NuScenes export of one frame's static+dynamic objects would be
schema-conformant in the narrowest sense but wouldn't represent what the
format is actually for, and building one now would mean inventing
placeholder ego-motion semantics with nothing real to back them. Revisit
once multi-frame temporal scenario generation exists -- not in
MASTER_PROMPT's roadmap as it stands.

### [DEFERRED] Sim2real distribution analysis not implemented
MASTER_PROMPT Section 3.7 lists "Sim2real distribution analysis" as a
bullet, and Section 1.1's architecture diagram lists a "Sim2Real
Validator (domain gap analysis)." Not implemented: doing this
meaningfully requires a real reference dataset to compare distributions
against (e.g. real building-height distributions, real traffic patterns),
and none exists anywhere in this codebase or its dependencies -- CLAUDE_
SKILLS_AND_PROMPTS.md's own Skill 13 (Sim2Real Validation) prompt template
explicitly expects the user to supply reference data, which nobody has
in this context. `sanity_checker.py`'s `check_building_height_distribution`
is the closest analogue actually implemented: it compares generated
output against the *configured* distribution (not a real-world one),
which is a real, useful check but not sim2real analysis in the sense the
spec means.

### [RESOLVED] COCO export only carried building/"structure" annotations
Was: `coco_exporter.py` declared exactly one category ("building"), since
no vehicle/pedestrian placement existed anywhere in the pipeline.
Resolved by `actor_placement.py` (see the ground-truth entry below):
`coco_exporter.py` now declares every category in
`src.ground_truth.categories` (building, sedan, suv, truck, bus,
pedestrian) and reads each annotation's real `category_id` from its
source `BoundingBox3D` rather than hard-coding `BUILDING_CATEGORY_ID`.
Cyclists are still not a category -- `ScenarioTypeConfig.vehicle_mix` has
no cyclist entry, and nothing in MASTER_PROMPT's roadmap asks for one.

### [RESOLVED] LiDAR ray-casting and depth-map rendering had no spatial acceleration structure
Was: `lidar_model.py`'s `LidarSensor.scan` and `depth_map.py`'s
`render_depth_map` were both O(rays * triangles) / O(pixels * triangles)
brute force -- every ray tested against every triangle of every mesh,
with tests kept deliberately small specifically because of this.

Resolved by `lidar_model.py`'s `TriangleGrid`: a uniform 3D grid built
once per scene (triangles binned into cells sized so each holds roughly
`target_triangles_per_cell` on average), then queried per ray via
Amanatides & Woo's 1987 voxel-traversal algorithm -- a ray only tests
triangles in the cells it actually passes through, walked in distance
order with early termination the moment a found hit is closer than the
next unvisited cell could possibly contain anything. This is an *exact*
acceleration structure, not an approximation: verified directly (200+
randomized scenes/rays plus explicit axis-aligned-ray and
`LidarSensor.scan`-level cases in `test_lidar_model.py`) to return
bit-identical results to the brute-force `closest_hit_distance` on the
same scene. `closest_hit_distance` itself is kept as the simple
reference implementation (and as what `TriangleGrid` is verified
against) but is no longer on either module's hot path -- both
`LidarSensor.scan` and `render_depth_map` build one `TriangleGrid` and
reuse it across every ray of the sweep/image, rather than rebuilding
(or re-scanning every triangle) per ray.

One subtlety worth recording: `LidarSensor.scan` only passes
`max_range_m` as the grid's search cutoff when `range_noise_std_m == 0`.
With noise enabled, a *true* hit just beyond `max_range_m` can still be
reported if noise happens to pull the measured range back within range
(a real noisy sensor could do the same) -- bounding the search to
`max_range_m` in that case would silently make such hits impossible to
find at all, changing behavior rather than just accelerating it.
**Action**: none -- `depth_map.py`'s `render_depth_map` has no analogous
range cutoff to worry about, so it always passes no `max_distance` limit.

### [RESOLVED] `TriangleGrid.closest_hit` silently dropped real hits on flat/coplanar geometry -- found via a genuine cross-platform CI failure
First push of `TriangleGrid` passed every test locally (Windows) but
`test_lidar_hit_points_lie_on_ground_plane` failed on GitHub Actions'
Ubuntu runner: `assert len(points) > 0` got `0`. Per this project's own
standing rule, the real CI log was pulled (pasted by the user, since this
environment's `gh` isn't authenticated and the Actions logs API returns
403 without admin rights) rather than guessed at -- and reproducing the
exact failing scan locally revealed the bug was real and
platform-*independent*, just triggered by different rays on Windows vs
Linux (1 of the scan's 3 elevation rings failed locally too; Linux's
`libm` cos/sin gave slightly different values that pushed more rings over
the same edge).

Root cause: a mesh entirely at one z value (a flat ground/road plane --
extremely common in this codebase) collapses the grid's own z-extent to
a single thin cell, so the geometry sits exactly on that cell's boundary.
`closest_hit` was checking each candidate triangle hit against `t_max`,
a bound computed from the grid's own AABB-slab-intersection formula --
a *different* formula from the Moeller-Trumbore ray-triangle math that
produced the actual hit distance. For a ray grazing that shared
boundary, the two formulas can disagree by a few ULPs, and when the
triangle-intersection result came out numerically *larger* than the
AABB-derived bound, the real hit was rejected by `hit <= t_max` even
though it was the closest (only) geometry there.

Fix: separated two bounds that had been conflated. `traversal_limit`
(from the grid's own AABB math) now only governs when to stop visiting
*new* cells; `accept_limit` (the caller's own `max_distance`, or
unbounded) is what a *found* triangle hit is actually checked against.
A hit discovered while testing a cell the traversal already legitimately
visited is accepted on the caller's own terms, not rejected against the
grid's internal, approximate bookkeeping. Added a regression test
(`test_triangle_grid_finds_hits_grazing_flat_scene_boundary`) pinning
the exact failing scan config, and strengthened
`test_lidar_hit_points_lie_on_ground_plane` from `len(points) > 0` to an
exact expected count, so a partial regression (some but not all rays
affected, as happened here) fails loudly instead of slipping through a
weaker assertion again.

### [DEFERRED] Segmentation mask rasterization is O(width * height) per object
`segmentation.py`'s `rasterize_instance_masks` runs one full-image
`matplotlib.path.Path.contains_points` pass per object (vectorized across
pixels, but not across objects). Correct and fine at test scale; a frame
with many buildings at HD resolution would be considerably slower than a
proper GPU/renderer-based approach. Same "revisit at real dataset scale"
note as the ray-casting entry above.

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

### [RESOLVED] No sensor noise model
Was: camera projection, LiDAR ray-casting, and depth rendering were all
perfectly noise-free; MASTER_PROMPT's own `camera_front.yaml`/
`camera_rear.yaml` config templates (Phase 0) already declared a
`distortion_model`/`distortion_coeffs` field that nothing read.

Resolved: `CameraIntrinsics.distortion_coeffs` (Brown-Conrady k1/k2/p1/
p2/k3, applied in `Camera.project` between normalization and the
intrinsic matrix -- standard OpenCV ordering/formula), `LidarConfig
.range_noise_std_m` (zero-mean Gaussian noise on each ray's measured
range, applied before the `max_range_m` check so noise can legitimately
both create and drop hits near the boundary), and `render_depth_map`'s
`noise_std_m` (same Gaussian treatment, applied only to finite/hit
pixels, clamped to stay positive). All three default to
off/`None`/`0.0` -- every pre-existing caller and test keeps behaving
exactly as before -- and every real sensor profile shipped in this repo
(`configs/sensor_profiles/*.yaml`) uses all-zero distortion coefficients
anyway, so this changes no default output anywhere in the pipeline.

`LidarSensor.__init__` and `render_depth_map` both raise `ValueError` if
their noise std is nonzero but no `seed` is given -- deterministic noise
requires a real seed, the same discipline every other generator in this
codebase already follows; no silent OS-entropy randomness sneaking into
an otherwise fully-reproducible pipeline.

Deliberately still out of scope:
- **Pixel quantization** for cameras: `bbox_2d.py`'s box-width/area math
  currently relies on sub-pixel-precision floats; explicitly rounding
  projected pixels to an integer grid would touch that math for
  uncertain benefit and wasn't asked for. Revisit only if a caller
  actually needs quantization-level realism.
- **Loading distortion coefficients from `configs/sensor_profiles/*.yaml`**
  at runtime: those files are still reference-only, exactly like the
  scenario templates were before `config_loader.py` (see that entry
  above) -- nothing reads them. Would need its own loader analogous to
  `load_scenario_config`, not attempted here since the ask was a noise
  *model*, not a sensor-config *loader*.

### [RISK] `UE5Backend`'s per-call connection setup makes the master prompt's <100ms/<2s latency budgets unverifiable as literally stated
`UE5Backend.call()` opens a brand-new WebSocket connection for every RPC
call (documented as a deliberate simplicity tradeoff in backend.py).
Measured directly and repeatedly against a local mock server: round-trip
time for the *same* call varied from well under 100ms to over 2 seconds
across otherwise-identical runs on this machine, with values landing
suspiciously close to whole seconds (e.g. 2.04s) -- consistent with
intermittent external interference on new local socket connections (most
likely antivirus real-time scanning on Windows), not a bug in the
request/response logic itself (which is 100% covered and passes every
functional test). The tests now assert only generous smoke-test bounds
(<5s) rather than the spec's literal targets.
**Action**: if real <100ms production latency is ever required, switch to
a persistent connection (connect once, reuse for many calls) rather than
per-call connect/disconnect -- this removes handshake cost from the
steady-state latency and would likely resolve the spec's target being
achievable in practice, though it doesn't explain the *variance* seen
here, which needs testing on a machine without the same local antivirus
configuration to confirm the root cause.

### [DEFERRED] LoadProceduralScenario C++ skeleton doesn't parse into mesh/traffic data yet
`AProceduralScenarioLoader::LoadProceduralScenario` (unverified, uncompiled --
see UE5 plugin gaps above) only validates that its input is well-formed
JSON. It does not dispatch per-mesh `UScenarioMeshBuilder::BuildMeshSection`
calls, initialize a traffic controller actor (no such class exists yet),
or implement streaming/culling -- MASTER_PROMPT Section 3.5's other three
"Procedural Meshes"/"Traffic Network" bullets for this phase. All three
need either a real UE5 project to build/profile against (streaming/
culling) or upstream pieces that don't exist yet (a traffic controller
actor class; Phase 6's orchestration layer, which is what would actually
produce the JSON payload this function receives). The JSON schema this
function expects is therefore provisional, not finalized against a real
producer.

### [DEFERRED] No actual UE5 `.uproject` still, and Phase 4's own first bullet (create it) not done
Same limitation carried from Phase 0/1's KNOWN_GAPS entries: no UE5.4
install exists in this environment, so nothing under `unreal_plugin/` has
ever been opened in the Unreal Editor or compiled. Phase 4 was the
roadmap's designated point to create the actual `.uproject` (MASTER_PROMPT
3.1.1); still not done, and shouldn't be attempted blind -- do this first,
manually, once UE5.4 LTS is actually installed somewhere, before trusting
any of the C++ under `unreal_plugin/`.

### [DEFERRED] Master prompt Section 3.4 (Phase 3) contradicts Section 1.1 on which language owns mesh generation
MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md Section 3.4 labels
"Procedural Meshes" as "(C++ in UE5)". Section 1.1's own architecture
diagram, by contrast, lists a "Procedural Mesh Factory (Geometry)" as
part of the Python-side "PROCEDURAL GENERATION ENGINE" box, distinct from
UE5's "Procedural Mesh Component (Real-time Generation)" in the C++
simulation backend. These directly conflict. Resolved in favor of the
testable interpretation: `src/procedural/mesh_factory.py` computes
vertex/triangle/UV buffers in Python; a minimal, unverified C++
`UScenarioMeshBuilder` class exists under
`unreal_plugin/.../ProceduralMesh/` as the UE5-side consumer of that data
(never compiled -- no local UE5 install, same limitation as the rest of
`unreal_plugin/`).

### [DEFERRED] Procedural material generation (asphalt, concrete, brick) and LOD system not implemented
MASTER_PROMPT Section 3.4 lists both under "Procedural Meshes." `Mesh.material`
is currently just a string name (`"asphalt"`, `"concrete"`) with no
backing material definition, parameter set (roughness/metallic per
QOL_RESEARCH_CHECKLIST.md Section D.2), or LOD levels -- there is no
rendering phase yet to consume any of that, and UE5 material assets can't
be authored/verified without the engine installed. Revisit in Phase 4+
once there's an actual UE5 project to define materials in.

### [DEFERRED] Building mesh has no roof geometry beyond a flat cap
`MeshFactory.build_building_mesh` extrudes a rectangular footprint
straight up with a flat roof quad -- no pitched/hipped roof, parapet, or
architectural detail. Reasonable for a first pass; MASTER_PROMPT gives no
building-detail spec to implement against.

### [RESOLVED] Lane connectivity across intersections was not implemented
Was: deferred twice -- Phase 2's `lane_topology.py` deferred it to Phase
3's traffic rules; Phase 3's `traffic_network.py` deferred it again
("full per-lane turn graphs are deferred further still"), since neither
phase had (or needed) the geometric classification logic to determine
which incoming lane legally feeds which outgoing lane at an intersection.

Resolved by `src/procedural/lane_connectivity.py`
(`LaneConnectivityGenerator`): for every (incoming edge, outgoing edge)
pair at a node (from `RoadNode.incoming_edges`/`outgoing_edges`, already
populated since Phase 1 but otherwise unused for this purpose), classifies
the movement STRAIGHT/LEFT/RIGHT from the signed angle between the
incoming edge's final heading and the outgoing edge's initial heading,
excludes U-turns (`outgoing_edge is incoming_edge.reverse_edge_id`), and
drops LEFT/RIGHT movements the incoming edge's own
`allows_turning_left`/`allows_turning_right` flag forbids -- both fields
existed, unused, since Phase 1 too. Lane-level (not just edge-level)
mapping follows `lane_topology.py`'s own right-hand-traffic convention
(lane 0 = median/left lane, highest index = curb/right lane): STRAIGHT
connects lanes index-for-index, LEFT only connects lane 0 to lane 0,
RIGHT only connects the outermost lane to the outermost lane -- a
defensible default absent any dedicated-turn-lane concept elsewhere in
this codebase.

Wired into `ScenarioResult.lane_connectivity` and `ScenarioValidator`
(basic regression checks: every connection's lane ids are real, no
lane connects to itself) alongside every other generator's output.
Deliberately still out of scope: this produces a connectivity *graph*
(which lane can legally reach which), not vehicle routing/path-following
behavior -- `ActorPlacementGenerator` still places vehicles statically at
spawn zones; nothing consumes this graph to actually move a vehicle
through an intersection yet. Revisit if/when vehicle animation/routing
is ever built -- this graph is exactly what that would need as its input.

### [DEFERRED] No parking spawn zones
MASTER_PROMPT Section 3.4 lists "spawn zones (driving, parking,
pedestrian)"; only driving and pedestrian are implemented.
`ScenarioType.PARKING_LOT`'s own geometry (parking stall lattice,
`configs/scenario_templates/parking_lot.yaml`'s `lattice_spacing_m` field)
isn't generated by any module yet -- there's nothing to place parking
spawn zones against. Revisit once parking-lot-specific layout generation
exists (not currently scoped to any phase in MASTER_PROMPT beyond the
taxonomy entry in Section 1.3).

### [DEFERRED] Master prompt Section 3.3 (Phase 2) has no algorithms, formulas, code, or tests -- unlike Phase 1
MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md's Phase 2 section is
literally four bullet points per sub-area (lane topology, building
placement) plus a one-line "Tests:" list of topics, with a note saying
"(Similar structure to Phase 1, with extensive mathematical formulations
and tests)" that is never actually delivered. This is a real gap in the
spec itself. `lane_topology.py` and `building_placement.py` were designed
from scratch this phase, informed by QOL_RESEARCH_CHECKLIST.md Section B.2
(lane boundaries) and B.3 (building placement), which do give concrete
formulas/example tests (with two more bugs of their own -- see Resolved).

### [DEFERRED] `ScenarioTypeConfig` has no field for road setback / sidewalk width
`building_placement.py`'s `ROAD_SETBACK_METERS = 2.0` is a fixed module
constant, not read from config, because no such field exists on
`ScenarioTypeConfig` (see scenario.py) and MASTER_PROMPT never specifies
one. A real per-scenario-type value (e.g. wider setback for
`urban_sparse`, none for `highway`) would need a new config field added
deliberately, not invented silently here.

### [DEFERRED] Building types/materials not assigned
MASTER_PROMPT Section 3.3 lists "assign building types, heights,
materials" -- heights are implemented (sampled from
`config.building_heights`); building *type* (residential/commercial/etc.)
and *materials* are not, since nothing downstream yet consumes them (no
mesh/rendering phase exists yet) and the spec gives no taxonomy for either.
Revisit when Phase 3's procedural mesh factory needs a building type to
pick a mesh/material from.

### [DEFERRED] Heavy/optional dependencies not yet in `pyproject.toml`
`open3d==0.17.0`, `ray==2.9.3`, `h5py==3.10.0`, `protobuf==4.25.1`,
`sphinx==7.2.6` + theme/mermaid ext, `py-spy`, `memory-profiler`,
`line-profiler` are specified in MASTER_PROMPT Section 2.2 but were left out
of Phase 0's `pyproject.toml` to keep the initial install fast and because
nothing in Phase 0-1 imports them.
**Needed by**: `open3d`/`h5py` — Phase 5 (sensors/ground truth); `ray` — Phase 6
distributed generation; `protobuf` — Phase 6 custom export; `sphinx*` — Phase 8
docs; profilers — whenever performance work starts.
**Action**: add to `pyproject.toml` in the phase that first imports them, then
re-run `poetry lock` and verify no version conflicts (open3d in particular has
had NumPy 2.x incompatibilities historically — must verify against pinned
NumPy 1.26.3).

### [DEFERRED] UE5 C++ plugin skeleton is unverified — cannot compile locally
`unreal_plugin/SyntheticDataGen/` (`.uplugin`, `Build.cs`, module
header/cpp) is structurally standard UE5 module boilerplate but has **never
been opened in Unreal Editor or compiled**, because UE5.4 is not installed in
this environment.
**Risk**: Build.cs dependency names, module loading phase, or C++20 flag could
be subtly wrong in ways only the UE5 toolchain would catch.
**Action**: first time someone has UE5.4 LTS installed (Phase 4 per roadmap),
open the project, add this plugin, and confirm `RunUAT.sh/.bat BuildPlugin`
succeeds with zero warnings before writing any further C++.

### [DEFERRED] No actual UE5 `.uproject` / editor project created
MASTER_PROMPT 3.1.1 calls for creating the UE5 project itself via
`RunUAT.sh BuildProject`. Not done — no UE5 installed here, and an empty
`.uproject` shell has little value without the editor to validate it.
**Action**: do this as the first step of Phase 4, not before — Phases 1-3 are
pure Python and don't need it.

### [RESOLVED] CI workflow (`.github/workflows/lint_and_test.yml`) had never actually run on GitHub Actions
Was: written to spec and known to work locally via Poetry, but never
exercised on an actual Actions runner, with open questions about
`poetry install`/codecov behaving differently there.

Resolved since Phase 7 (see the `pkg_resources`/Ray entry below, found via
a real Actions run on commit `4c06f02`): every push since has run on
GitHub Actions and is confirmed green, including every commit through
`434378e` (CLI + config loader). This entry was left stale for several
commits after that -- a reminder to keep this file in sync with reality,
not just append to it.

### [DEFERRED] Docker/Kubernetes deployment (MASTER_PROMPT Section 2.4) not started
Not needed until Phase 6+ distributed/cloud scaling. No action needed yet.

### [DEFERRED] Sphinx documentation site (`docs/`) is an empty directory with only `.gitkeep`
MASTER_PROMPT 3.1.3 lists `docs/conf.py`, `index.rst`, etc. Deferred to
Phase 8 (Documentation & Release) per the roadmap — premature to scaffold
Sphinx before there's any API surface to document.

### [BLOCKER-for-later] Delaunay-based `RoadNetworkGenerator` cannot handle (near-)collinear node layouts — breaks the Highway scenario category
Discovered while chasing a coverage gap in Phase 1: `scipy.spatial.Delaunay`
raises `QhullError` ("Initial simplex is flat") whenever all input points are
exactly collinear, which `road_network.py::_connect_nodes` now catches and
re-raises as `ValueError` (see `test_collinear_points_raise_value_error_not_qhull_error`
in `tests/unit/test_road_network.py`).
**Why this matters**: MASTER_PROMPT Section 1.3 Category 3 (Highway) is
explicitly defined as "only parallel edges (no intersections)" — i.e.
nodes laid out in straight lines. The current grid-perturbation step adds
Gaussian noise that makes *exact* collinearity astronomically unlikely, so
generic urban-style bounds/config won't hit this — but a straight highway
segment's own generation logic (not yet written; belongs later in Phase 1
scenario-type-specific generation or Phase 2) will need either (a) a
non-Delaunay connectivity strategy for parallel/highway layouts, or (b) a
guaranteed transverse jitter large enough to keep Qhull's simplex
non-degenerate while staying visually "straight."
**Action**: do not reuse generic `RoadNetworkGenerator._connect_nodes`
unmodified for `ScenarioType.HIGHWAY` without addressing this. Revisit when
implementing scenario-type-specific road generation.

### [RISK] `_find_or_create_node` is O(N) per call / O(N^2) total for grid merging
Documented in its own docstring as an acceptable tradeoff at the scenario
sizes targeted (hundreds of nodes), confirmed fine by
`test_large_scenario_performance` (2000m x 2000m bounds completes well
under the 10s budget). Revisit with a `scipy.spatial.KDTree` if/when Phase
1 performance tests are run at the "10,000+ scenarios" scale mentioned in
MASTER_PROMPT's scalability requirements, or if bounds grow past ~5km.

### [DEFERRED] City-block identification approximates blocks as individual surviving Delaunay triangles
`BuildingPlacementGenerator._identify_blocks` reuses the same Delaunay
triangulation `RoadNetworkGenerator` computes internally and treats each
triangle whose 3 edges all survived length-filtering as one "block."
Real city blocks are usually quadrilateral-ish regions spanning several
adjacent triangles, not single triangles -- a general planar-graph
face-finding algorithm (walking the graph to recover actual bounded faces)
would be more realistic but is substantially more work than anything else
specified for this phase (which gives no algorithm at all -- see above).
This approximation is geometrically valid (triangles are simple,
non-overlapping polygons that correctly partition the interior) but will
produce visibly triangular block shapes rather than rectangular ones.
Revisit if/when a mesh-rendering phase makes block shape visually matter.

## Resolved

### [RESOLVED] Root `ARCHITECTURE.md` was stale — Phase 8
Written in Phase 0, before `RoadNetworkGenerator` switched from
`numpy.random.RandomState` to `numpy.random.Generator`/`PCG64` (Phase 1,
to support the master prompt's own `2**63-1` seed test requirement).
`ARCHITECTURE.md` still claimed every generator used `RandomState`,
silently wrong since Phase 1. Replaced with a short pointer to the new
`docs/architecture.rst`, which reflects the system as actually built
across all 7 completed phases (and is far more likely to be kept current
going forward, since it's part of the Sphinx build every push now
implicitly re-checks via `test_docs_build.py`).

### [RESOLVED] Sphinx docs (deferred since Phase 0) now built, and real bugs in the docstrings it exposed — Phase 8
Added the Sphinx toolchain (`sphinx`, `sphinx-rtd-theme`,
`sphinxcontrib-mermaid`) and wrote `docs/conf.py` +
`{index,api_reference,user_guide,architecture,performance_tuning,
release_notes}.rst`. API reference pages are generated by `autodoc` +
`napoleon` directly from this codebase's own (already-thorough)
docstrings -- no hand-duplicated API docs to drift out of sync.
Building surfaced two real problems, neither hypothetical:
(1) `napoleon`'s default "Attributes" rendering for dataclasses
(`RoadNode`, `BoundingBox3D`, `LidarConfig`, etc.) collided with
`autodoc`'s own separate documentation of the same fields, producing 20+
literal "duplicate object description" warnings on the first build --
fixed via `napoleon_use_ivar = True`;
(2) `segmentation.py`'s `rasterize_instance_masks` docstring's
hand-written `Returns` type text (`Dict[int, npt.NDArray[np.bool_]]`)
got parsed by napoleon as an attempted cross-reference and broke the
build with `ERROR: Unknown target name: "np.bool"` -- fixed by wrapping
it in double-backtick literal formatting instead of relying on
napoleon's automatic type-role conversion for that line, and by
switching `autodoc_typehints` from `"description"` to `"signature"`
globally to avoid this whole class of issue recurring for other type
annotations. Final state: `sphinx-build -b html` succeeds with **zero**
warnings (`-W` mode, warnings-as-errors, passes clean), verified via a
real test (`test_docs_build.py::test_docs_html_build_succeeds`), not a
one-off manual run.
`docs/user_guide.rst`'s code examples are real `.. doctest::` blocks --
every printed value was verified by actually running the example script
first (not guessed), then `sphinx-build -b doctest` genuinely executes
all 13 of them on every test run via
`test_docs_build.py::test_docs_doctest_examples_execute_correctly`. This
directly satisfies MASTER_PROMPT Section 3.9's own "Documentation builds
without errors" and "Code examples in docs execute correctly" test
bullets as real, CI-enforced checks, not documentation that could
silently drift stale.

### [RESOLVED] CI failed on Phase 7's first push: `ModuleNotFoundError: No module named 'pkg_resources'` inside Ray — root cause confirmed via user-provided log
`main` commit `4c06f02` (Phase 7) went red on GitHub Actions' `test` job
despite passing locally against a genuinely fresh clone on this machine.
This session had no way to fetch the actual failure log itself (repo API
returned `403 Must have admin rights to Repository`, no `gh` auth
available, no Docker to reproduce Ubuntu locally) -- an initial fix
attempt (capping `ray.init(object_store_memory=...)` against the
well-known "small `/dev/shm` on CI" Ray failure mode) was applied as a
reasonable but unconfirmed hypothesis and did **not** fix it. The user
then pasted the actual CI log, which showed the real error: every
`ray.remote(...).remote()` call failed with
`ModuleNotFoundError: No module named 'pkg_resources'`, raised from deep
inside `ray/_private/pydantic_compat.py`'s unconditional
`from pkg_resources import packaging` (triggered the first time Ray sets
up its serialization context for a submitted task).
Root cause: `pkg_resources` ships as part of `setuptools`, and
`setuptools` was never declared as an explicit dependency anywhere in
this project -- it was only present by transitive/environment accident,
and evidently absent (or present without `pkg_resources`) in whatever
`setuptools` version the CI runner's poetry-managed venv actually got.
Attempting the straightforward fix (`poetry add setuptools`) made it
**worse**: it resolved to the newest available `setuptools` (84.0.0),
which -- confirmed by reproducing the exact same
`ModuleNotFoundError: No module named 'pkg_resources'` locally after that
install -- has itself now removed `pkg_resources` entirely, as part of
setuptools' own ongoing deprecation of that API (import warns "slated
for removal as early as 2025-11-30"). Fixed by pinning `setuptools<81`
(landed on 80.10.2), the last major line confirmed locally to still ship
an importable `pkg_resources` (with the deprecation warning, not an
error). Verified for real: `tests/integration/test_distributed_runner.py`
(the exact 3 tests that failed in CI) now pass locally, and the full
290-test suite plus lint/mypy all pass clean.
**Process note**: this took two attempts precisely because the first fix
was applied without ever seeing the real error -- a plausible, well-
justified guess is not a substitute for the actual log. Logged honestly
as a hypothesis at the time (see the entry that used to be here); once
the user provided the real traceback, the actual fix took one attempt.
See the two [RISK] entries above (setuptools pin fragility, Ray's own
future `pkg_resources` removal) for what could still break this later.

### [RESOLVED] Resumable generation produced colliding annotation IDs across scenarios — found in Phase 7
`resume_handler.py`'s checkpoint design writes each scenario's COCO
contribution to its own small JSON "part" file via
`export_coco([frame])`, called independently per scenario. Since
`coco_exporter.export_coco`'s annotation-ID counter starts at 1 for every
call, every part file's own annotations restarted numbering at 1 --
merging parts naively produced multiple annotations across different
scenarios/images sharing the same `id`, a direct violation of
QOL_RESEARCH_CHECKLIST.md Section H.1's "no ID collisions" check (which
`coco_exporter.py`'s own tests already enforce for the *non*-resumable
path, but this manual reconstruction bypassed that guarantee). Caught
directly: `test_resumable_generation_from_scratch_matches_sequential`
failed with mismatched annotation dicts differing only in `id`, and
tracing it down confirmed actual ID collisions, not just a numbering
offset. Fixed by renumbering every annotation's `id` sequentially
immediately after merging all parts, regardless of whether each part was
freshly generated or loaded from a prior run -- bbox/segmentation/category
content is untouched, only the `id` field changes. Verified via
`test_checkpoint_restores_correctly_after_simulated_crash`, which
confirms a crashed-then-resumed run produces byte-identical output
(including annotation IDs) to an uninterrupted run.

### [RESOLVED] Added `pycocotools` and `pandas-stubs` dev dependencies — Phase 6
`pycocotools==2.0.7` installed cleanly on Windows (pre-built wheel
available) and is used for real schema validation of COCO exports
(`test_coco_schema_valid_per_pycocotools` loads the export through the
actual reference `pycocotools.coco.COCO` parser, not just hand-written
structural checks). `pandas-stubs` was added rather than reaching for
the same `ignore_missing_imports` blanket-override pattern used for
scipy (Phase 1) -- pandas has a well-maintained stubs package, so
`sanity_checker.py`'s pandas usage gets real `mypy --strict` type
checking instead of being waved through.

### [RESOLVED] Bare `poetry run pytest` doesn't discover brand-new source files until `poetry install` is re-run — found in Phase 5
Confirmed by direct, repeated testing: after adding a new file under
`src/` (e.g. `src/sensors/camera_model.py`), `poetry run pytest
tests/unit/test_camera_model.py` failed with `ModuleNotFoundError: No
module named 'src.sensors.camera_model'`, even though `.venv/Scripts/
python.exe -m pytest` (same venv, same test) and `poetry run python -m
pytest` both succeeded immediately. Existing (previously-added) test
files were unaffected by bare `poetry run pytest` -- only brand-new
modules triggered it. Root cause not fully diagnosed (something about how
the `pytest.exe` console-script entry point resolves the editable
install's package contents differs from `python -m pytest`), but running
`poetry install` again reliably fixed it every time it was tried.
**Action**: run `poetry install` after adding any new file under `src/`,
before trusting a bare `poetry run pytest` run of tests that import it.
`python -m pytest` (or `poetry run python -m pytest`) appears unaffected
and can be used as a workaround if `poetry install` is inconvenient.

### [RESOLVED] Road network nodes could end up outside the caller's declared bounds — found via Phase 4's ScenarioValidator
Discovered by `ScenarioValidator`'s own first real end-to-end test
(`test_full_generated_scenario_is_valid`) actually failing on a routine
generated scenario: node positions up to ~70m outside a 500m-wide bounds
region. Root cause, present since Phase 1 and never previously tested:
(1) `_generate_grid_points` can overshoot the requested bounds by up to
one full grid `spacing` per axis by construction (`np.arange(x_min, x_max
+ spacing, spacing)` always includes `x_min + spacing`, previously noted
in this file only as a "grid points guaranteed >= 2 per axis" quirk, not
recognized as a bounds violation in its own right); (2) Gaussian
perturbation in `_perturb_grid` can push any point further out, with no
containment check anywhere in the pipeline. Fixed by adding
`RoadNetworkGenerator._keep_within_bounds`, called after perturbation:
reflects any out-of-bounds point back across the violated edge (not a
hard clip, which would collapse every overshooting point on the same
side onto one exact boundary line -- for 3+ points, an exactly collinear
configuration that crashes Delaunay triangulation, a real failure mode
already established via `test_collinear_points_raise_value_error_not_qhull_error`).
A final `np.clip` is kept as a safety net for the practically-unreachable
case where reflection alone isn't enough. Verified with
`test_all_node_positions_within_bounds` and a 20-seed parametrized
variant, plus the originally-failing validator integration test now
passing.

### [RESOLVED] Forward/reverse road edges got independently-sampled, often-mismatched lane counts — found in Phase 3
QOL_RESEARCH_CHECKLIST.md Section G.1's own `test_lane_count_consistent`
asserts a directed edge and its reverse counterpart must have the same
`num_lanes`. Checked directly against Phase 1's `_assign_road_attributes`
(unchanged since Phase 1, not previously tested for this property): 76 of
118 edges in a routine urban_dense/500m test scenario had mismatched
forward/reverse lane counts, road types, and speed limits, because the
master prompt's reference implementation (and this codebase's Phase 1
port of it) samples each directed edge's attributes independently. Fixed
in `road_network.py::_assign_road_attributes` by computing attributes
once per undirected road and applying them identically to both directed
edges of a bidirectional pair, tracked via a `processed_edge_ids` set.
Added `test_forward_reverse_edge_attributes_match` as a regression test.
This mattered enough to fix now (rather than deferring) because Phase 3's
`TrafficNetworkGenerator` builds spawn zones and a navigation graph
directly on top of `num_lanes`/`speed_limit_kmh` -- building on
inconsistent data would have baked the bug one layer deeper.

### [RESOLVED] QOL checklist's own `test_lane_boundary_perpendicular` example asserts the wrong property — Phase 2
QOL_RESEARCH_CHECKLIST.md Section B.2 gives an example test asserting the
*boundary polyline's own segment direction* is perpendicular to the
*centerline's segment direction* (`dot(c_dir, l_dir) ~ 0`). Verified
empirically against a correct parallel-offset boundary implementation:
the actual dot product comes out ~0.9999 (nearly parallel), not ~0 --
which makes sense, since a road's edge line runs *alongside* its
centerline, not perpendicular to it. This is a bug in the checklist's own
example, not in the implementation. `math_utils.py`'s
`compute_lane_boundaries` and its tests (`test_math_utils.py`) implement
and check the actually-correct properties instead: the boundary is
parallel to a straight centerline, and the *offset vector* (boundary
point minus centerline point) is perpendicular to the local direction at
unambiguous (endpoint) points.

### [RESOLVED] Building placement took >10s and never reliably terminated in reasonable time — Phase 2
First implementation of `BuildingPlacementGenerator.generate` hung for
over a minute on a routine urban_dense/500m bounds test case (confirmed by
direct timing, not assumed). Root causes, both real and stacked: (1)
`target_count` per block sometimes reached the hundreds for a single large
triangle, and the loop paid the full `MAX_PLACEMENT_ATTEMPTS_PER_BLOCK`
cost even long after a block was effectively full; (2) every placement
candidate was checked for overlap against *every building placed in every
block so far* (`existing_buildings`), an unnecessary O(total_buildings^2)
cost across the whole scenario, not just within one block. Fixed with (1)
an early-exit after `MAX_CONSECUTIVE_FULL_FAILURES` consecutive slots each
exhaust every attempt (signal a block is full without exhausting
`target_count`), and (2) checking new candidates only against the current
block's own `placed` list -- justified because Delaunay triangle interiors
never overlap and (once the setback bug below was also fixed) no building
can cross into a neighboring block, so cross-block overlap is
geometrically impossible without an explicit check. Verified: 769
buildings generated in 0.52s post-fix vs. >60s (killed) before, on the
identical scenario.

### [RESOLVED] Road setback check missed roads passing near the *middle* of a building's side — Phase 2
While fixing the above, restricting the setback check to only a block's
own 3 triangle edges (for speed) caused `test_no_building_within_road_setback`
to actually fail: a building's corner came within 1.81m of a road,
violating the 2.0m `ROAD_SETBACK_METERS`. Root cause: for a
skinny/obtuse Delaunay triangle, a road segment that is *not* one of that
triangle's own 3 edges can still pass within the setback distance of a
point deep inside it. Fixing that (checking every real road segment,
spatially pre-filtered by a cheap padded-AABB test for speed) then
exposed a second, independent bug: the setback check itself only tested
distance from the building footprint's 4 *corners* to each road segment,
which misses a road running near-parallel to, and close beside, the
*middle* of one of the footprint's sides -- confirmed as the actual cause
of `test_no_building_to_building_overlap` failing (two buildings on
opposite sides of a shared road overlapped because neither one's corners,
specifically, were close enough to trip the corner-only check). Fixed by
replacing the corner-distance check with `_segment_intersects_aabb`
(slab-method segment-vs-box intersection) against the footprint's AABB
inflated by the setback distance -- the geometrically correct formulation
of "does anything about this road come within `ROAD_SETBACK_METERS` of
this box." Both tests now pass; see
`test_segment_intersects_aabb_near_parallel_to_one_side` for a test that
specifically reproduces the missed case.

### [RESOLVED] `tests/performance/` untracked by git — broke CI on first push
Phase 0's `.gitkeep`-placeholder pass (adding placeholders so empty
scaffold directories survive git, which doesn't track empty dirs) missed
`tests/performance/`. It existed on local disk the whole time — created
during scaffolding and never deleted — so every local test run before this
found it and passed, masking the problem entirely. A fresh `git clone`
(exactly what GitHub Actions does) never had it, so
`test_required_directory_exists[tests/performance]` failed there, which
surfaced as the "Lint and Test / test" check going red on the first push
(commit `a70a381`) while "lint" passed. Fixed by adding
`tests/performance/.gitkeep` (commit `fefdccc`) and verifying by cloning
the repo to a clean temp directory and re-running the exact CI command
(`poetry run pytest --cov=src --cov-report=xml --cov-fail-under=90
tests/`) before pushing — confirmed 69/69 pass there before trusting it.
**Process takeaway**: "tests pass locally" is not sufficient evidence for
a scaffold/structure test suite when the working tree has accumulated
directories across a session — a local run can pass on stale disk state
that git never actually captured. From here on, verify state-sensitive
test suites (anything checking file/directory existence) against a fresh
clone, not just the in-place working tree, before pushing.

### [RESOLVED] Coverage gate now exercised against real logic — Phase 1
The Phase 0 note about `--cov-fail-under=90` only being checked against an
empty `src/` tree is stale: `road_network.py` (199 stmts) and `scenario.py`
(48 stmts) now exist, and `poetry run pytest --cov=src` reports 97% overall
(96% on road_network.py) — a real, non-vacuous pass of the 90% bar. Verified
via `poetry run pytest --cov=src --cov-report=term-missing`, not just CI.

### [RESOLVED] `ScenarioTypeConfig`/`ScenarioType` were referenced but never defined in the master prompt
MASTER_PROMPT Section 3.2.2's test fixtures construct
`ScenarioTypeConfig(...)` and Section 3.1.3's file tree lists
`src/procedural/scenario.py`, but the document never actually defines
either the `ScenarioType` enum or the `ScenarioTypeConfig` schema/fields —
a genuine gap in the spec itself, not something I overlooked. Filled in
`src/procedural/scenario.py`: a `ScenarioType` str-enum matching Section
1.3's six categories, and a pydantic `ScenarioTypeConfig` model with the
fields implied by the fixtures (`avg_block_size`, `num_intersections`,
`building_density`, `vehicle_mix`, etc.), plus validators for range
ordering, density bounds, and vehicle-mix-sums-to-1. Covered by
`tests/unit/test_scenario.py` (14 tests, 100% coverage).

### [RESOLVED] `np.random.RandomState` seed range too small for the master prompt's own test requirement — Phase 1
The master prompt's Section 3.2.2 `test_seed_coverage_edge_cases` requires
`seed=2**63-1` to work, but confirmed by direct test:
`np.random.RandomState(2**63 - 1)` raises `ValueError: Seed must be between
0 and 2**32 - 1`. This is a genuine bug in the master prompt's own
reference implementation, not a hypothetical. Fixed in
`RoadNetworkGenerator.__init__` by switching to
`np.random.Generator(np.random.PCG64(seed))`, which accepts arbitrary-size
non-negative integer seeds via `SeedSequence` while remaining fully
deterministic. Verified: `test_seed_coverage_edge_cases` now passes for
seeds `[0, 42, 12345, 2**32-1, 2**63-1]`.

### [RESOLVED] Dataclass default `__eq__` crashes on numpy-array fields — Phase 1
Confirmed by direct test: a `@dataclass` with a `numpy.ndarray` field raises
`ValueError: The truth value of an array with more than one element is
ambiguous` on `==` comparison, because the generated `__eq__` chains
per-field `==` with `and`. The master prompt's `RoadNode`/`RoadEdge`
dataclasses have `position`/`centerline` ndarray fields and a custom
`__hash__`, but don't disable the default `__eq__` — meaning any code path
that compares two instances (e.g. `in` on a list, or an assertion) would
crash. Fixed by declaring both `@dataclass(eq=False)`; identity is via
`node_id`/`edge_id` through the manual `__hash__` only, and no code path
needs value-equality on these objects.

### [RESOLVED] Node/intersection classification used raw directed-edge degree instead of road-connection count — Phase 1
Found while investigating a coverage gap (the `degree == 3` T-junction
branch was never hit by any test). Root cause: every road is always
created as a *bidirectional pair* of directed edges
(`_create_edge_pair`), so `len(incoming_edges) + len(outgoing_edges)` is
**always even** for every node — the master prompt's own
`degree == 3 -> T_JUNCTION` condition is therefore mathematically
unreachable, and its `degree >= 4 -> FOUR_WAY` condition silently
mislabels genuine 3-way intersections (which have degree 6) as four-way.
Confirmed empirically: sampling degrees across a generated network showed
only even values (4, 6, 8, 10, ...), never 3. Fixed in
`_assign_road_attributes` by classifying on `degree // 2` (the actual
number of distinct connected roads) instead of raw degree. Added
`test_three_way_junction_classified_as_t_junction` and strengthened
`test_node_types_assigned_correctly` to assert degree is always even before
halving it. This also changes `_assign_road_attributes`' lane/speed
heuristic, which used the same (buggy) raw-degree comparison for its
`start_degree >= 3` branch.

### [RESOLVED] `scipy.spatial.qhull.QhullError` import path is deprecated
`from scipy.spatial.qhull import QhullError` (used in some scipy example
code and easy to reach for) emits a `DeprecationWarning` on scipy 1.11.4 —
confirmed by direct import test. Used `from scipy.spatial import
QhullError` instead (the supported public path).

### [RESOLVED] `mypy --strict` had no path for scipy (no py.typed marker) or bare `np.ndarray` — Phase 1
scipy 1.11.4 ships no type stubs, so any module importing `scipy.spatial`
failed `--strict` with `import-untyped`. Added a `[[tool.mypy.overrides]]`
block in `pyproject.toml` scoped to `module = "scipy.*"` with
`ignore_missing_imports = true`. Separately, bare `np.ndarray` field/return
annotations failed `type-arg`; replaced with `numpy.typing.NDArray[np.float64]`
throughout `road_network.py`.

### [RESOLVED] `poetry install --no-root` left `import src` unresolvable in the test venv — Phase 1
Phase 0 ran `poetry install --no-root` (to skip installing the project
itself as a package, since there was no code in `src/` yet worth
installing). Once `tests/conftest.py` added a shared fixture that imports
`from src.procedural.scenario import ...`, pytest failed with
`ModuleNotFoundError: No module named 'src'` — the poetry venv never had
the project's own package installed. Fixed by running plain `poetry
install` (no `--no-root`), which installs `synthetic-av-dataset-gen`
itself in editable mode per `pyproject.toml`'s `packages = [{include =
"src"}]`. Contributors setting up fresh should use `poetry install`, not
`--no-root`, from Phase 1 onward.

### [RESOLVED] Poetry install/lint/test flow — Phase 0
Original entry said Poetry wasn't installed and the flow was unverified.
Installed Poetry 1.7.1 via `pip install --user`, ran `poetry install`
(succeeded, `poetry.lock` generated and committed), then `poetry run pytest
--cov=src` (33/33 pass) and `scripts/run_linter.sh` (black/isort/pylint/mypy
--strict all clean, pylint 10.00/10) — all against the real Poetry-managed
environment, not just a bare pip venv.
**Residual note**: `poetry` was not on PATH after a `pip install --user` on
this Windows machine; `scripts/run_linter.sh` now falls back to
`python -m poetry` when the `poetry` executable isn't found. Contributors on
other machines should confirm `poetry` resolves normally, or rely on the
fallback.
**Update (Phase 4)**: partway through this session, `python` on PATH
started resolving to this project's own `.venv/Scripts/python.exe`
(created for early Phase 0 experimentation) instead of the system Python
that actually has Poetry installed -- so `python -m poetry` itself broke
(`No module named poetry`), even though the fallback logic above was
designed for the opposite problem (poetry missing from PATH, not python
resolving to the wrong installation). Cause not fully diagnosed (likely
some shell/session state change unrelated to this repo). Worked around by
invoking Poetry via its full system path
(`C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python.exe -m
poetry ...`) directly rather than trusting `python -m poetry`. Anyone
hitting `No module named poetry` should check `where python` first -- it
may not be the interpreter Poetry is installed against.

### [RESOLVED] pylint/mypy never run against real code — Phase 0
`tests/unit/test_project_initialization.py` initially had 8 missing-docstring
warnings and one import-outside-toplevel warning (pylint score 7.56/10).
Fixed by adding a one-line docstring to every test function and moving the
`toml` import to module level. Now 10.00/10, mypy --strict clean.
