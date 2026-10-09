### [RESOLVED] Crossing pedestrians floated above the road; most pedestrians looked like they were standing still

User dispatched a deep-debugging agent (static analysis only, editor
wasn't running) which found the real root cause of the first bug and a
strong, later-confirmed hypothesis for the third of three reported
symptoms (the second, an fps concern, was accepted as likely a real
rendering cost, not investigated further).

**Floating on the road (CONFIRMED, then live-verified after the fix)**:
`_pedestrian_to_asset_json` set every pedestrian's Z to
`SIDEWALK_TOP_HEIGHT_METERS` unconditionally, including `CROSSING`-zone
pedestrians who are placed ON the road, not the sidewalk -- `Pedestrian`
had no field recording which zone type placed it, so that information
never reached serialization. Fixed: `Pedestrian` gained `surface_z`,
set by the two placement methods (`_try_place_sidewalk_pedestrian` ->
`SIDEWALK_TOP_HEIGHT_METERS`, `_try_place_crossing_pedestrian` -> new
`PEDESTRIAN_ROAD_SURFACE_Z_METERS = 0.0`, matching how vehicles are
already placed) and threaded straight into the serializer instead of
the old hardcoded constant. Live-verified: `DebugListActorsWithMesh`
showed both real crossing pedestrians in a loaded scenario at
`Z=0.000` (previously `Z=10.800`), and a ground-level screenshot shows
feet flush with the crosswalk surface, no visible gap.

**"They walk for a few seconds then stand still" (real finding, not
what it first looked like)**: live-tested the debugging agent's
"`Animate=True` unlocked continuous real-time playback" hypothesis
directly -- screenshotted the same pedestrian actor twice, 8 real
seconds apart, in the live PIE session: pixel-identical both times.
That hypothesis is REFUTED; poses are correctly frozen, confirmed
twice now (once right after the original fix, once again here). Also
checked for a leftover City Sample Mass AI crowd system in the test
level (`DebugListActorsWithMesh` for `CrowdCharacter`/`SKM`/`Mass`
mesh substrings) -- zero found, ruling that out too.

The REAL explanation, found by sweeping and visually classifying many
individual `Frame` values via live side-profile screenshots (not
guessed): a real 320-frame walk cycle's own "passing" phase (both feet
momentarily close together) is a genuine part of walking, but a
uniformly random `Frame` pick across the whole cycle lands on that
near-neutral phase often enough to read as "standing still" at a
glance -- especially since NOTHING in this project moves over time, so
a pedestrian's ONE frozen frame is all a viewer ever sees of them.
Swept roughly every 10-20 frames across both baked clips plus a finer
5-frame sweep around the one confirmed-good region: frames 0, 80,
120-135, 240 all read near-neutral; frame 160 read as a clearly wide,
dynamic mid-stride pose, with 140-155 trending toward it. Clip 1
(320-429) was swept at 6 points spanning its full width and read as
near-neutral EVERY single time -- unlike clip 0, it never showed a
convincing walking stride anywhere tested.

Fix: `city_sample_assets.py` gained `PEDESTRIAN_WALKING_FRAME_RANGE =
(140, 190)`, a live-verified-as-walking sub-range of clip 0 only (clip
1 dropped from pose sampling entirely); `_build_pedestrian` now samples
`pose_frame` from this range instead of a random clip's full width.
This is a single window bracketing the one confirmed peak, not an
exhaustive map of the full 430-frame space -- documented honestly as
such in the constant's own docstring, since a real gait cycle typically
has two extended-stride phases per stride and only one was located and
confirmed here.

Both fixes live-verified together in one real generated scenario (43
pedestrians, 2 on real crosswalks): crossing pedestrians at the correct
road-level Z, and a wide render showing genuinely varied, clearly
walking-looking stances rather than a uniform standing crowd. New tests
`test_pedestrian_surface_z_matches_zone_type` and the updated
`test_pedestrian_pose_frame_is_real_and_diverse` cover both fixes. Full
suite green (561/561), pylint 10.00, mypy --strict clean.

