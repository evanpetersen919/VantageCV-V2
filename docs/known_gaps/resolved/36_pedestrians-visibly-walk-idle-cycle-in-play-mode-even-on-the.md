### [RESOLVED] Pedestrians visibly walk/idle-cycle in Play mode even on the real, non-live-preview dataset-capture path

User reported pedestrians animating (idle a few seconds, then visibly
walk) in a scenario loaded WITHOUT `enable_live_pose_preview` -- i.e.
on the path that is supposed to be a single frozen, deterministic pose
per pedestrian. This directly threatens the project's core
reproducibility requirement (a captured frame must be a function of
the scenario seed, not of wall-clock time), so it was investigated
heavily rather than dismissed as cosmetic.

**Real, hard-evidence findings, in the order they were established:**

1. **Not the live-preview component.** `obj list class=
   PedestrianWalkCycleComponent` repeatedly showed 0 live instances
   while the animation was still visibly happening -- ruled out
   immediately, correctly, early.

2. **A real methodology bug that produced a long run of false
   "it's frozen" readings.** Every automated screenshot-based
   verification this session (via the `TakeScreenshot`/
   `DebugMoveCameraTo` RPCs, run from an unfocused window since the
   controlling terminal holds OS focus, not the game) showed the pose
   completely static, contradicting the user's live, focused
   observation and two screen recordings they provided. Bringing the
   game window to actual OS foreground before repeating the identical
   automated test immediately reproduced the same real motion the user
   saw. Root cause: Unreal throttles/reduces game time updates while
   the window lacks OS focus, so wall-clock time barely advances
   during an unfocused automated test even though real wall-clock
   seconds pass. **Any future live-verification of animation timing in
   this project must bring the game window to OS foreground first**
   (see the `SetForegroundWindow`/`ShowWindow` PowerShell snippet used
   this session) -- screenshots taken while unfocused are not reliable
   evidence of "frozen."

3. **Real root cause, found via direct engine node-graph inspection
   (`obj dump` on the live objects, not assumed):** `/Game/Crowd/VAT/
   MaterialFunctions/GetFrame`'s own graph has a `StaticSwitch` whose
   condition is the `Animate` static bool parameter. Per Unreal's own
   `UMaterialExpressionStaticSwitch::Compile` source
   (`Engine/Source/Runtime/Engine/Private/Materials/
   MaterialExpressions.cpp`): `return bValue ? A.Compile(Compiler) :
   B.Compile(Compiler);`. `A` is a real, purely time-driven chain
   (`Clamp(Time - TimeStartOffset, 0) * Playrate * SampleRate`, fed by
   a real `MaterialExpressionTime` node) with **no connection to
   "Frame" at all**; `B` is `FunctionInput_3`, literally named
   `"Frame"` -- a plain, non-time-dependent passthrough. `Animate=True`
   (set earlier this same session, and required at the time for
   "Frame" to have any visible effect at all -- see the "[RESOLVED]
   Pedestrian pose/activity diversity" entry above) selects `A`,
   discarding "Frame" entirely at the shader level. This is a genuine,
   sourced fact, not a guess.

4. **The only edit that provably changed the live-rendered result:**
   directly setting `DefaultValue=False` on the shared layer's own
   `MaterialExpressionStaticBoolParameter_1` node inside `/Game/Crowd/
   VAT/Materials/ML_BoneAnimation` itself (via `unreal.load_object` +
   `get/set_editor_property("DefaultValue")`, run through a headless
   `-ExecutePythonScript` editor pass -- NOT the live `-game` RPC
   session, since a similar edit attempted live crashed the engine
   once via GPU device-lost, a known flakiness pattern in this
   environment already documented elsewhere in this file, most likely
   triggered by a heavy synchronous shader recompile happening
   alongside an already-rendering scene). This DID freeze the one
   pedestrian mesh tested, confirmed via a rigorous, window-focused,
   camera-recentered timelapse.

5. **The fix does NOT fully propagate, and this is the actual open
   gap.** Individual per-character/per-outfit-piece
   `MaterialInstanceConstant` assets (593 found under `/Game/Crowd`,
   confirmed via `unreal.AssetRegistryHelpers`) each carry their OWN
   explicit instance-level override for `Animate`
   (`bOverride=True, Value=True`), which takes precedence over the
   shared layer default regardless of what the layer's own default is
   set to. Two separate scripted attempts to clear/flip this specific
   per-instance override were made, neither crashed, both reported
   success, and **neither actually changed the on-disk value** (directly
   re-verified via `obj dump` after each, both still showing
   `Animate: Value=True, bOverride=True` on the exact same test
   asset): (a) `unreal.MaterialEditingLibrary.
   set_material_instance_static_switch_parameter_value(mic, "Animate",
   False)` alone; (b) the same call followed by `unreal.
   MaterialEditingLibrary.update_material_instance(mic)` (this second
   attempt visibly did much more work -- 85s across 593 assets vs 10s
   for the first -- but still did not change the verified value). This
   matches a fact already established earlier this same session
   (`set_material_instance_static_switch_parameter_value` "silently
   fails for both GLOBAL_PARAMETER and LAYER_PARAMETER association" on
   layer/nested-function-sourced parameters) -- now confirmed to also
   survive a follow-up `update_material_instance` call, and to survive
   even when reported as a successful save.

6. **A separate, real, and independently disproven hypothesis:**
   `FScenarioAssetData`'s pedestrian spawn path
   (`VehicleActorSpawner.cpp`) calls
   `Component->SetCustomPrimitiveDataFloat(2, 0.0f)` on spawn, on the
   theory that the `GetFrame` call's "Playrate" input is wired to a
   `MaterialExpressionPerInstanceCustomData` node at `DataIndex=2`
   (confirmed via `obj dump` on that exact expression). Live-verified
   this write has **zero effect on the actual rendered animation
   speed**: setting it to 0 and, separately, to an extreme 1000 (which
   should cycle roughly 94x/second if correctly wired) produced
   visually indistinguishable motion over the same short window. The
   custom-primitive-data index/write is not reaching the real shader
   input, for a reason not yet found. Left in the code (harmless,
   possibly one contributing factor among several) but is NOT, by
   itself, a fix.

**The actual fix, found immediately after the above was written up as an open gap:**

The two scripted per-instance override attempts (point 5 above) both
had the SAME real bug, found by reading `UMaterialEditingLibrary::
SetMaterialInstanceStaticSwitchParameterValue`'s own C++ implementation
(`Engine/Source/Editor/MaterialEditor/Private/MaterialEditingLibrary.cpp`)
rather than more guessing: its Python-exposed wrapper,
`set_material_instance_static_switch_parameter_value`, takes an
`association` parameter that defaults to
`MaterialParameterAssociation.GLOBAL_PARAMETER`. Every prior call this
session omitted it. Since "Animate" is specifically
`Association=LayerParameter, Index=0` (confirmed via `obj dump` many
times over), every prior "fix" was silently writing a harmless,
unused `GlobalParameter`-associated "Animate" entry that nothing reads,
while the real `LayerParameter`-associated entry -- the one `GetFrame`'s
function call actually wires to -- was never touched. This is exactly
why every previous attempt reported success (the call really did
succeed, against the wrong parameter) yet visibly changed nothing.

Fixed by calling `set_material_instance_static_switch_parameter_value(
mic, "Animate", False, unreal.MaterialParameterAssociation.
LAYER_PARAMETER)`, immediately followed by `unreal.MaterialEditingLibrary
.update_material_instance(mic)` (`MarkPackageDirty` +
`PreEditChange`/`PostEditChange` + `UpdateStaticPermutation`) before
`EditorAssetLibrary.save_loaded_asset(mic)` -- the `update_material_
instance` call turned out to be a second, independently necessary
step: a save without it reported success and even rewrote the
`.uasset` file's timestamp, but a genuinely fresh process re-reading
that "saved" file from disk still showed the old value (verified
several times, isolating the discrepancy to the save path specifically
before finding this missing call).

Applied via a headless `-ExecutePythonScript` pass (not the live
`-game` RPC session, per the established crash-avoidance pattern) to
the real, complete set of 215 material instances this project's own
pedestrian pipeline actually uses (enumerated from a live scenario's
own real spawned `MaterialInstanceDynamic` names, not guessed) --
notably NOT all 593 assets under `/Game/Crowd` in general, since that
superset includes unrelated `TrafficDriver` vehicle-material variants.
The script waits 120s after the edit loop before quitting, since an
earlier attempt that quit immediately (10s for 215 assets) also failed
to persist -- static-switch changes trigger a real, and apparently
not-optional-to-wait-for, asynchronous shader recompile.

**Live-verified end to end, properly this time**: a completely fresh
process (no in-memory carryover) reading the saved asset from disk
shows `Animate` correctly resolved to `false`. With the game window
brought to genuine OS foreground (see point 2's methodology finding),
a pedestrian's pose is now pixel-identical across a properly-focused,
camera-recentered timelapse (multiple runs, ~7.5-9.6s apart), AND a
live 5-pedestrian cluster shot still shows genuinely diverse stances
(no collapse to one shared pose) -- both the freeze and the
per-instance "Frame" diversity work correctly together. User confirmed
live: "they are all frozen now."

**Cleanup after the real fix landed**: the two workaround mechanisms
built while chasing this (both now unnecessary, since the content
itself is correct) were removed: `UPedestrianPoseFreezeComponent` (a
per-tick "Frame" reassertion component -- pointless once the shader
isn't drifting the value on its own) and the `SetCustomPrimitiveDataFloat`
/`"Playrate"` scalar-override code (proven to have zero real effect on
this content, per point 6 above -- left in briefly as "harmless" but
removed since it no longer serves any purpose and only obscures the
real fix's location). `UPedestrianWalkCycleComponent` (the opt-in,
live-preview-only feature) is unaffected and still correct: it works
by writing "Frame" directly on the branch this fix keeps selected
(`Animate=false`'s manual passthrough), so continuous live-preview
motion still functions exactly as designed.

**If a future session touches `/Game/Crowd`'s materials again**: the
real, working technique is `set_material_instance_static_switch_
parameter_value(mic, name, value, association)` -- ALWAYS pass
`association` explicitly (check via a real `obj dump` what association
the target parameter actually uses; do not assume `GLOBAL_PARAMETER`)
-- followed by `update_material_instance(mic)` before saving, and wait
for shader compilation (tens of seconds, scales with asset count)
before the process exits. Skipping either the association or the
`update_material_instance` call, or quitting too early, all independently
produce a false "it worked" (no crash, no error, save reports success)
that only a genuinely fresh process re-reading from disk reveals as
unchanged.

