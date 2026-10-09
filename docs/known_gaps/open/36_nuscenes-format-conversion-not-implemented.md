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

