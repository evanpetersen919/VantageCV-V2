### [RESOLVED] "Always standing then walking, in sync" persisted after the first fix -- real root cause was the range itself, not animation

User reported the same-day fix above didn't hold: pedestrians still
looked like they stood for a few seconds then walked, in sync across
the whole crowd. Explicitly asked for heavy re-debugging, evidence-
backed only. Two mechanisms that would explain real synchronized
movement were directly tested and CONCLUSIVELY REFUTED with hard
evidence, not re-assumed correct from the earlier pass:

1. **Continuous real-time playback from the `Animate=True` content
   fix**: re-ran the same-actor-over-time test with a much longer
   window (60 real seconds, not 8) -- pixel-identical before and after,
   twice. Also checked for a leftover City Sample Mass AI crowd system
   in the test level (`DebugListActorsWithMesh` for `CrowdCharacter`/
   `SKM`/`Mass` substrings) -- zero found.
2. **LOD/distance-based World Position Offset disabling** (a real,
   well-known UE5 mechanism: `UStaticMeshComponent::
   WorldPositionOffsetDisableDistance` stops WPO evaluation beyond a
   set distance, which could make a pedestrian's baked pose "pop"
   between the set Frame and the mesh's raw undeformed geometry as a
   moving player crosses that threshold -- explaining both "changes
   after walking a few seconds" and "in sync," since every instance
   would share the same default threshold). Found the real object path
   for a live pedestrian's `StaticMeshComponent` (`obj list class=
   StaticMeshComponent`, since `DebugListActorsWithMesh`'s "label" is a
   display label, not the real object path) and `obj dump`'d it
   directly: `WorldPositionOffsetDisableDistance=0` (never disabled),
   `bEvaluateWorldPositionOffset=True`. Conclusively rules this out too.

With both animation-over-time mechanisms disproven by direct engine
evidence, re-examined the STATIC per-instance pose quality itself
instead. Root cause: the first pass's window (140-190) was based on a
coarser sweep and its own tail (175-190) turned out, at finer
resolution, to ALSO be near-neutral -- a real gait cycle's dynamic
"extended stride" phase is a much smaller fraction of the cycle than
the passing phase surrounding it. Several of those tail frames were
independently confirmed by checking a real generated scenario's actual
`pose_frame` distribution: 4 separate pedestrians had sampled exactly
`190`, now known to render near-neutral. Additionally, the narrow
26-value window caused frequent EXACT-duplicate frames among many
pedestrians (multiple pairs sharing values like 145, 146, 150, 152,
155, 156, 172, 173) -- a second, real, non-time-based contributor to
"these all look the same," entirely independent of any animation
question.

Densely re-swept the full 430-frame space (every 5-20 frames, each
point individually confirmed via a live side-profile screenshot: a
back/front view does not reliably show gait phase, since fore-aft leg
separation isn't visible from those angles -- side profile is
required). Found and confirmed TWO real dynamic windows this time:
`140-165` (six points swept, all dynamic in one continuous row) and
`280-290` (280 and 290 both confirmed dynamic, 270 and 300 confirmed
neutral on either side). A candidate third window at frame 220 was
also dynamic, but both neighbors 10 frames either side (210, 230) were
neutral -- too narrow a confirmed span to trust, deliberately left out
rather than guessed into a window.

Fix: `PEDESTRIAN_WALKING_FRAME_RANGE` (singular) replaced with
`PEDESTRIAN_WALKING_FRAME_RANGES` (both confirmed windows).
`ActorPlacementGenerator._sample_pose_frame` picks a window then a
frame within it, and re-rolls (bounded to 8 attempts, never unbounded)
against the immediately PRECEDING pedestrian's own frame -- targeting
specifically the case a person would actually notice (two neighbors,
placed in sequence along the same real sidewalk/crossing zone,
captured in the same glance), not a full scenario-wide duplicate
tracker. New test `test_pedestrian_pose_frame_avoids_immediate_repeat`
checks zero consecutive repeats in placement order. Live-verified: a
real scenario's pose_frame distribution went from 24 distinct values
(39 pedestrians, several from a since-disproven-neutral tail) to real,
confirmed-dynamic values only, zero consecutive duplicates. Full suite
green (562/562), pylint 10.00, mypy --strict clean.

**Honest disclosure**: the original "in sync" report is still not
explained by any mechanism found in this codebase -- every avenue that
could cause a pose to change over time or with camera distance has now
been checked and ruled out with direct evidence (frozen at both 8s and
60s; `WorldPositionOffsetDisableDistance=0`; no Mass AI actors present).
The best-supported remaining explanation is that walking past many
different frozen pedestrians -- some of which, under the OLD range,
genuinely did render near-neutral (the confirmed-standing tail) -- and
noticing frequent near-identical duplicates (also now reduced) together
produced the perception, without any actual synchronized animation
existing to find.

