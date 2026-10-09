### [RESOLVED] Real pedestrians via City Sample's VAT crowd meshes, replacing box placeholders
User asked to prioritize pedestrians next (the single most safety-critical
class for an AV-perception dataset, and previously a plain grey box with
an explicitly-documented placeholder material -- see
`configs/material_tags.json`'s `pedestrian` entry). Heavily researched
before implementing anything, per this project's own evidence standard.

**Why not `BP_CrowdCharacter`** (City Sample's own crowd Blueprint):
confirmed via a direct source read of `Source/CitySample/Crowd/
CrowdCharacterActor.h` that its native parent, `ACitySampleCrowdCharacter`,
lives in City Sample's own game-project *source*, not portable content --
the exact same wall vehicles hit with `ACitySampleVehicleBase` (see the
Phase 0 entry above). Real, useful side-finding from that same source
read: unlike vehicles, City Sample's crowd `AnimInstance` chain
(`UCitySampleAnimInstance_Crowd` -> `UMassCrowdAnimInstance`) has **no
hard Mass AI/ZoneGraph/StateTree runtime dependency** for a stationary
actor's pose -- it only reads `CharacterMovementComponent->Velocity`,
which is zero for a placed-and-frozen actor, driving the animation state
machine to Idle deterministically. Epic's own `ACrowdCharacterLineup`
class (a static review-grid spawner) confirms Epic itself spawns these
characters with zero runtime simulation for non-gameplay purposes. This
means a full skeletal-mesh-plus-AnimBP pedestrian is technically
possible without Mass AI -- but still needs new skeletal-mesh spawn C++
this project doesn't have.

**What was actually used instead**: `Content/Crowd/VAT/` -- Vertex
Animation Texture static meshes (animation baked into a texture, sampled
by the material; driven by the `AnimToTexture` engine plugin, confirmed
shipped with UE5.4 itself at `Engine/Plugins/Experimental/AnimToTexture`,
not previously enabled in `VantageCV_UE5.uproject`). Being a plain static
mesh with no skeleton, it has the same "no pose dependency, renders
unconditionally" property that made `SM_Frame_<vehicle>` work for
vehicles -- and drops straight into the exact same `"static_asset"`
spawn path already used for vehicles/facade pieces, with **zero new C++**.

Migrated one real asset (`SM_f_tal_nrw_combined` -- female, normal-weight,
one pre-assembled outfit, no body/clothing part assembly needed) via
Epic's Migrate tool (166 files, 676MB, mostly shared MetaHuman
skin/material dependencies later variants will reuse). **Real, measured
bounds** via `GetStaticMeshBounds` (not the old placeholder guess):
depth 0.96m / width 0.33m / height 1.68m -- replaces the old
`PEDESTRIAN_WIDTH/DEPTH/HEIGHT_METERS = 0.5/0.5/1.7` guess.

**Live-verified, not just spawn-logged** (this project's own established
standard, after the vehicle investigation's lesson that a clean spawn
log is not evidence of a correct render): a close screenshot showed a
real, natural mid-stride walking pose -- one leg forward, weight-bearing,
arms relaxed, correct human proportions -- with no skeleton, AnimBP, or
Mass AI involved at all. Then verified end-to-end in a real generated
city scenario (13 pedestrians, real traffic/crosswalks/buildings): a
wide shot and a close shot both show correctly-scaled human figures on
the sidewalk/crosswalk alongside vehicles, at their real sidewalk-offset
spawn positions.

**Code changes**: `city_sample_assets.py` gained `PEDESTRIAN_ASSET_PATHS`
(currently one entry -- more gender/weight/outfit variants are a real,
deliberate fast-follow for visual diversity, not done yet).
`Pedestrian` (`actor_placement.py`) gained an `asset_path` field, sampled
deterministically like `Vehicle.asset_path`. `dataset_generator.py` no
longer builds a pedestrian box mesh into `ScenarioResult.meshes`
(`MeshFactory.build_pedestrian_mesh` stays for its own tests/fallback,
same precedent as `build_vehicle_mesh`); ground truth is unaffected,
since `extract_bboxes_3d_pedestrians` derives boxes from `Pedestrian`'s
own placement-time fields, never from mesh geometry.
`scenario_serializer.py` gained `_pedestrian_to_asset_json`, appending
pedestrians to `"assets"` as `"static_asset"` entries (no `part_paths`,
same as a facade piece -- unlike a vehicle's body-plus-parts assembly).

**Real gap found and flagged, not yet fixed**: pedestrian placement is
still very sparse -- exactly one spawn slot per directed edge
(`traffic_network.py::_generate_spawn_zones`), at one fixed point, unlike
street furniture which tiles multiple items along a sidewalk run. A real
sidewalk should hold a variable number of people distributed along its
length. Also not yet done: pose diversity (the VAT material's `GetFrame`
material function strongly suggests a frame/time parameter could pick a
different baked pose per instance -- untested).

**Update (same session): added the male variant for gender diversity.**
`SM_m_tal_nrw_combined` -- the only other fully pre-assembled "combined"
mesh City Sample ships (every other weight/outfit combination only
exists as separate body+clothing pieces, not yet investigated for
assembly) -- migrated (676MB -> still 676MB, only 5 new files: the
shared MetaHuman skin/material dependencies were already pulled in by
the female migration). Real measured bounds differ genuinely from the
female mesh (1.81m tall vs 1.68m), so `PEDESTRIAN_DIMENSIONS_METERS`
(`city_sample_assets.py`) now keys per-asset-path dimensions, mirroring
`VEHICLE_DIMENSIONS`'s per-type approach, rather than one shared
placeholder box -- `ActorPlacementGenerator._try_place_pedestrian` looks
up each sampled pedestrian's own real dimensions after choosing its
asset. Live-verified twice: an isolated side-by-side spawn showed the
male mesh visibly taller than the female one, then a real generated
scenario showed both variants placed correctly (12 pedestrians, mixed
genders) alongside vehicles/buses/lit traffic signals. New test
(`test_pedestrian_asset_path_and_dimensions_are_consistent`) asserts
every placed pedestrian's dimensions match its own asset's real bounds,
not a mismatched pairing.

Full suite green (557/557) after adding/updating tests across
`test_actor_placement.py`, `test_bbox_3d.py`, `test_mesh_factory.py`,
`test_validator.py`, and `test_scenario_serializer.py` for the new
`Pedestrian.asset_path` field and its real measured dimensions.

