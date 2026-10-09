### [RESOLVED] Pedestrian pose/activity diversity, and the real reason the obvious fix didn't render anything

Deep research before any code, per explicit request: confirmed the real
per-mesh frame layout by directly querying every real pedestrian asset's
own `AnimToTextureDataAsset` (`Content/Crowd/VAT/Data/DA_*`, one per
mesh, mirroring the mesh's own name) via a headless CitySample session
-- not the earlier session's untested `GetFrame` guess. All 123 real
body/top/bottom/shoe/face assets this project uses share the exact same
layout, zero exceptions: `NumFrames=430` at 30fps, two baked clips,
frames 0-319 (a walk cycle) and 320-429 (a second distinct baked pose,
confirmed by a live render, not assumed from the frame count alone --
turned out to also be a walking cycle, just a different one, not a
categorically different activity like standing/texting). Hair meshes
have no `DA_` of their own (real, checked asymmetry) but share the exact
same `Frame`/`NumFrames`/etc. parameter set via the same
`ML_BoneAnimation` material layer as everything else (confirmed via
`MaterialEditingLibrary.get_scalar_parameter_source`), so one `Frame`
value applies coherently across a whole pedestrian's body+outfit+hair.

**Implementation** (all real, evidence-backed, zero guessing): added
`FScenarioAssetData::MaterialScalarOverrides` (`TMap<FString, float>`)
to the C++ asset schema, parsed from a new optional
`"material_scalar_overrides"` JSON field (same optional-field pattern as
`part_paths`); `ApplyMaterialScalarOverrides` in
`VehicleActorSpawner.cpp` creates a `UMaterialInstanceDynamic` per
material slot (not just slot 0 -- a live query found crowd FaceMeshes
have a separate eye-refractive material on their own slot) and calls
`SetScalarParameterValue` for each override, applied identically to the
body AND every `PartPaths` component so a pedestrian's whole outfit
stays synchronized. Python side: `PEDESTRIAN_ANIM_NUM_FRAMES`/
`PEDESTRIAN_ANIM_CLIPS` in `city_sample_assets.py` (the real, 123-asset-
verified constants); `Pedestrian.pose_frame` sampled once per instance
in `_build_pedestrian` (uniform over a randomly chosen clip, giving both
"how they're moving" -- stride-phase variety within a clip -- and "what
they're doing" -- which of the two distinct baked clips); serialized as
`"material_scalar_overrides": {"Frame": pose_frame}` in
`_pedestrian_to_asset_json`.

**Real bug found and fixed, not a guess that happened to work**: this
mechanism, live-tested exactly as built, had ZERO visible effect --
three pedestrians with different `Frame` values rendered pixel-
identical, twice, reproducibly. Two false leads chased and REJECTED
with real evidence before finding the true cause (documented so a
future session doesn't re-chase them): (1) suspected Custom Primitive
Data override (`bUseCustomPrimitiveData`) intercepting the named
parameter -- checked the real engine header
(`MaterialExpressionScalarParameter.h`) for the actual field names, then
used the engine's own `obj dump <object>` console command (via the
already-existing `DebugConsoleCommand` RPC) against each of the 8 real
scalar-parameter expression objects inside `ML_BoneAnimation` (found via
`obj list class=MaterialExpressionScalarParameter`, since UE Python's
`get_editor_property` cannot list a `MaterialFunctionMaterialLayer`'s
own expression graph under any property name tried) -- all 8 showed
`bUseCustomPrimitiveData=False`, ruling this out conclusively, not by
assumption. (2) suspected Nanite-fallback-breaks-WPO (a real, already-
documented pattern in this exact file for tree leaf cards under
`-d3d11`) -- checked via the same `obj dump` technique on the body
static mesh itself: `NaniteSettings=(bEnabled=False,...)`, already off,
ruled out.

**Real root cause**: `obj dump` on the material INSTANCE (not the
scalar parameters, the STATIC SWITCH parameters this time) found three
switches gating the entire pose-driving shader branch, ALL defaulting
to `False` in the migrated content: `Animate`, `UseFourInfluences`
(matching the DA's own real `NumBoneInfluences=FOUR`), and `UseUV1`
(matching the DA's own real `UVChannel=1`). Static switches are baked
into the shader PERMUTATION at compile time -- a `MaterialInstanceDynamic`
cannot override them at runtime no matter what value is set, which is
exactly why the otherwise-correct MID mechanism above had no visible
effect. `MaterialEditingLibrary.set_material_instance_static_switch_
parameter_value` -- the API that should fix this -- silently fails
(returns `False`) for these specific parameters, for both `GLOBAL_
PARAMETER` and `LAYER_PARAMETER` association, since they resolve through
a Material Attribute Layer/nested Material Function rather than being
declared directly on the base Material; a real, confirmed UE5 Python API
gap, not a mistake in usage (tried both associations, checked the raw
`static_parameters` property directly -- not exposed to Python either).

**Fix, scoped to avoid shared-content risk**: `Animate` and
`UseFourInfluences` are both defined inside `/Game/Crowd/VAT/Materials/
ML_BoneAnimation` -- a real PROJECT-owned asset (this project's own
migrated content, not shared engine content) -- found via `obj list
class=MaterialExpressionStaticBoolParameter`/`...StaticSwitchParameter`
inside that asset and edited directly: loaded each expression sub-object
by its exact path (e.g. `ML_BoneAnimation.ML_BoneAnimation:
MaterialExpressionStaticBoolParameter_1`) and set its own `DefaultValue`
property to `True` via ordinary `get_editor_property`/`set_editor_
property` (which works fine on the leaf expression object itself, unlike
the broken per-instance override convenience API), then saved the asset.
`UseUV1`, by contrast, is defined inside the shared ENGINE plugin
(`Engine/Plugins/Experimental/AnimToTexture/Content/Materials/
MaterialFunctions/TexCoord.uasset`) two call-levels deep -- editing it
would affect every project on this machine using this engine install,
so it was deliberately NOT touched. Tested empirically instead of
guessing whether it was actually needed: after fixing only the two
project-owned switches, three pedestrians with different `Frame` values
rendered three genuinely distinct walking poses live -- `UseUV1`'s
default apparently already resolves to usable data for this content, so
the riskier engine-content edit was correctly avoidable, not skipped out
of expedience.

**Live-verified end-to-end**: a real generated scenario (41 pedestrians)
produced 38 distinct sampled `pose_frame` values (real diversity, not a
constant default); a wide shot of the resulting crowd shows visibly
varied stances, not a uniform robotic line. New test
`test_pedestrian_pose_frame_is_real_and_diverse` checks every placed
pedestrian's `pose_frame` falls inside a real clip range and that a
real config/seed produces more than one distinct frame. New serializer
tests check `"material_scalar_overrides"` is present with the correct
`Frame` value for pedestrian entries and absent for vehicle/facade
entries. Full suite green, pylint 10.00, mypy --strict clean.

**Lesson for future material/content investigation**: when a runtime
per-instance override (MID scalar, or any similar mechanism) has zero
effect despite being wired correctly, check STATIC parameters
(switches/bools) before assuming the wiring itself is wrong -- static
parameters are baked into the shader permutation and are invisible to
any runtime override, a fundamentally different failure mode from "the
override isn't reaching the shader." The engine's own `obj list`/
`obj dump` console commands (already available via this project's
`DebugConsoleCommand` RPC) can enumerate and inspect ANY loaded
UObject's real properties by exact sub-object path, including nested
material expression graphs UE Python's `get_editor_property` cannot
reach directly -- a strictly more powerful ground-truth tool than
guessing at Python property names when reflection hits a wall.

