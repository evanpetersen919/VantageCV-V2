### [RESOLVED] City Sample asset integration Phase 1 (Python side): vehicles sample real City Sample asset paths, no longer build box meshes
Follow-up to the Phase 0 entry above. Vehicles are the highest-priority
category in the integration plan (confirmed-compatible, ~13 real
models, most visually impactful fix) and the first to actually swap
away from procedural box geometry.

`src/procedural/city_sample_assets.py` (new) catalogs real
`VEHICLE_ASSET_PATHS`, keyed by the same vehicle-type strings
`ActorPlacementGenerator` already samples from `vehicle_mix`
(sedan/suv/truck/bus) -- confirmed real (not guessed) via direct
inspection of City Sample's installed content: every non-hero vehicle
folder has a `BP_veh*_Sandbox.uasset` Blueprint. The sedan/suv split is
a documented, deliberately-flagged-as-unverified assignment (City
Sample's folder names don't distinguish body types); flagged for
revisit during this phase's manual PIE verification pass.

`Vehicle` (`actor_placement.py`) gained an `asset_path: str` field,
sampled deterministically alongside `vehicle_type` via the actor's
existing seeded RNG. `dataset_generator.py`'s `generate_scenario` no
longer builds a box mesh per vehicle (`MeshFactory.build_vehicle_mesh`
still exists, used by its own tests and as a documented fallback shape,
just no longer feeds `ScenarioResult.meshes`); ground truth is
unaffected, since `extract_bboxes_3d_vehicles` derives boxes from
`Vehicle`'s own placement-time fields, not from mesh geometry --
confirmed via reading `validator.py`'s `_validate_meshes` (no
cross-check against vehicle count) and grepping the test suite for any
exact-mesh-count assertion that would have broken.

`scenario_serializer.py`'s `"assets"` array (present but empty since
Phase 0) is now populated with one entry per vehicle:
`{"category": "vehicle", "asset_path", "position", "rotation_rad",
"id"}` -- the schema decided in the integration plan.

**C++ side, real end-to-end verification against a live standalone UE5
session (2026-09-16), including two real bugs found and fixed along the
way**:

1. The user manually migrated the 14 chosen `veh*_Sandbox` Blueprints
   (via Epic's Migrate tool) from `CitySample` into `VantageCV_UE5`'s
   Content (2,850 files copied -- the full dependency closure).
2. First real spawn attempt: `LoadClass<AActor>(nullptr, *AssetPath)`
   failed for all 14 vehicles ("spawned 0 asset(s), skipped 50").
   **Real bug, fixed**: `LoadClass` needs the full object path to a
   Blueprint's generated class (`"<package path>.<asset name>_C"`), not
   the bare package path -- fixed in `VehicleActorSpawner.cpp` by
   building that path explicitly.
3. Second attempt still failed, and the engine log revealed the real,
   deeper blocker: every `BP_veh*_Sandbox`'s parent chain ultimately
   depends on `ACitySampleVehicleBase` -- a native C++ class defined in
   **CitySample's own game-project source**
   (`Source/CitySample/Vehicles/CitySampleVehicleBase.h`), not portable
   content. Reading that file confirmed it's deeply wired into
   CitySample's own gameplay framework: Mass AI traffic control
   (`IMassTrafficVehicleControlInterface`), Enhanced Input, a custom
   UI/menu system, photo mode, `ACitySampleCharacter` -- porting it
   would mean dragging in a large, open-ended slice of a game framework
   this project has no use for (scenarios are frozen-frame captures,
   not driveable).
4. **Architectural decision (user-approved after being presented with
   three options: build a minimal custom actor, port
   `ACitySampleVehicleBase` and its dependency chain, or fall back to
   box meshes)**: `UVehicleActorSpawner` was rewritten to spawn a plain
   `AActor` holding just the vehicle's real combined skeletal mesh
   (`SKM_<vehicle folder>`, e.g.
   `/Game/Vehicle/vehCar_vehicle02/Mesh/SKM_vehCar_vehicle02`) via a
   `USkeletalMeshComponent` -- no vehicle movement component, no
   Blueprint class, no gameplay dependencies at all. This is genuinely
   portable content (confirmed via direct inspection of every migrated
   vehicle's `Mesh/` subfolder) and is everything a frozen-pose
   synthetic scene actually needs.
   `src/procedural/city_sample_assets.py`'s `VEHICLE_ASSET_PATHS` was
   updated to point at these skeletal mesh paths instead of the
   `_Sandbox` Blueprint paths.
5. **Real, live confirmation**: rebuilt (`Build.bat`, 0 failed),
   relaunched standalone (`-game -d3d11`, which also starts the RPC
   subsystem -- same `GameInstanceSubsystem` mechanism PIE uses), sent
   a real 112-mesh `urban_dense` scenario over the WebSocket bridge.
   Engine log confirmed: `LoadProceduralScenario: built 112 mesh
   section(s), skipped 0` and `LoadProceduralScenario: spawned 50
   asset(s), skipped 0` -- all 50 placed vehicles spawned successfully,
   no errors/warnings in the load window. (No screenshot/visual capture
   was taken -- there's no RPC method for that yet; log-based
   confirmation of spawn success/positions was judged sufficient for
   this phase, not worth building new screenshot infrastructure for.)

`ProceduralScenarioLoader.cpp` gained `ParseAssetData` (parses one
`"assets"` entry, converting `position` via the existing
`ApplyCoordinateConvention` and negating `rotation_rad`'s sign for the
same mirror-transform reason Y is negated) and a dispatch loop that
spawns one vehicle per `category: "vehicle"` entry; `"prop"`/
`"hero_building"` entries are skipped (not fatal) until later phases
add them.

**Still open, tracked for this phase's completion**: the bbox-precision
spot-check (do the real skeletal mesh silhouettes diverge meaningfully
from the placement-time box across the 14 models?) that decides whether
Phase 7 needs pulling forward -- not yet done, since it needs either a
real screenshot/viewport comparison or an in-editor visual check.

Full suite (458 tests, up from 451) and lint clean.

