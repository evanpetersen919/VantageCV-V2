### [RESOLVED] Reversed the curated-window fix above: full real walk cycle + a real "standing" activity for dataset capture, plus an opt-in live-preview animation for interactive QA

The curated-window fix immediately above was itself re-examined once
the user clarified the actual long-term goal: this is a research-grade
AV-perception **dataset generator**, and the real requirement is that a
captured frame must not show every pedestrian frozen in the same
narrow, "obviously mid-stride" pose. Real street photography is not
dominated by dramatic mid-stride shots -- most real pedestrian photos
show subtler stances -- so restricting capture to the 37 hand-picked
"dynamic" frames was optimizing for a human's live-viewing perception,
not for a statistically representative training dataset, and it
artificially capped true diversity. This is a same-day reversal of the
fix directly above; kept both entries so a future session sees the
full reasoning trail rather than re-litigating it.

This also revisited a fact established earlier the same day and never
fully acted on: every real pedestrian asset's 430-frame VAT clip splits
into two baked sub-clips, `(0,319)` and `(320,429)`. A dedicated sweep
of the second clip (6+ points, all confirmed) found it consistently
reads as a distinct, genuinely different near-static pose across every
point tested -- not a broken clip, but very likely a real
"standing/idle" activity, distinct from "walking."

**Part A -- dataset capture (deterministic, no new C++,** `city_sample_assets.py`**/**`actor_placement.py`**):**
`PEDESTRIAN_WALKING_FRAME_RANGES` (the curated windows) removed.
`PEDESTRIAN_WALKING_CLIP = (0, 319)` and `PEDESTRIAN_STANDING_CLIP =
(320, 429)` (both aliases onto the already-real, already-verified
`PEDESTRIAN_ANIM_CLIPS`) sample from the FULL real walk cycle.
`PEDESTRIAN_STANDING_ACTIVITY_FRACTION = 0.2` (disclosed ESTIMATE -- no
real survey data of sidewalk activity mix was found) gives sidewalk
pedestrians a real chance of a "standing" pose instead of walking;
crossing pedestrians are always sampled from the walking clip only
(definitionally walking). `_sample_pose_frame` keeps the existing
bounded (8-attempt) re-roll against the immediately preceding
pedestrian's frame. Live-verified on a real 801-pedestrian scenario:
643 walking / 158 standing (~20%, matching the target fraction).

**Part B -- live preview (opt-in, interactive QA only, new C++):** the
real, long-term ask ("all pedestrians walk the entire time") requires
genuine continuous animation, which this material was empirically
proven NOT to support on its own (`Playrate`/`bLooping`/
`TimeStartOffset` do not drive any live-time WPO evaluation path --
tested: set, screenshotted 3s apart, pixel-identical). Real animation
therefore needs a per-actor `Tick()`. This is architecturally isolated
from the actual dataset-capture path: a new optional per-asset JSON
field, `"enable_live_pose_preview"` (absent = false, matching this
project's established "optional field, absence means off" convention),
is threaded through `serialize_scenario`'s own new
`enable_live_pose_preview` parameter (default `False`). The real
dataset-generation pipeline (`dataset_generator.py`) never passes it,
so every real captured payload is byte-for-byte unaffected -- the
load-bearing safety property, since a research dataset's captured frame
must be a deterministic function of the scenario's seed, never of
wall-clock elapsed time.

New `UPedestrianWalkCycleComponent` (`PedestrianWalkCycleComponent.h`/
`.cpp`): `PrimaryComponentTick.bCanEverTick = true`; on `BeginPlay`
picks a random per-instance start offset via `FMath::RandRange`
(deliberately non-deterministic -- this component only ever exists on
the explicitly opt-in, non-reproducible live-preview path); on
`TickComponent`, advances the frame at the real, already-established
30fps sample rate and calls `SetScalarParameterValue(TEXT("Frame"),
...)` on every stored MID, wrapping strictly within whichever clip
(walking or standing) that pedestrian was originally assigned --
derived from the existing `Frame` override already present in
`MaterialScalarOverrides` (< 320 vs. >= 320), so a "standing" pedestrian
never visibly strides. `VehicleActorSpawner.cpp`'s
`ApplyMaterialScalarOverrides` now returns the MIDs it creates (previously
discarded) so `SpawnVehicle` can hand them to this new component when
`AssetData.bEnableLivePosePreview` is set. `ProceduralScenarioLoader.cpp`
parses the new field the same optional way as `PartPaths`/
`MaterialScalarOverrides`.

Live-verified end to end after rebuild: (1) regression -- a real
scenario loaded WITHOUT the flag, same actor screenshotted 5s apart,
pixel-identical (default dataset-capture path untouched); (2) with the
flag, the same actor's pose visibly changed 5s later (arm position
shifted); (3) two different pedestrians screenshotted at the same
instant showed different, desynced poses (not lockstep) -- confirming
the per-instance random phase offset works as designed. Full suite
green (532/532), pylint 10.00, mypy --strict clean.

