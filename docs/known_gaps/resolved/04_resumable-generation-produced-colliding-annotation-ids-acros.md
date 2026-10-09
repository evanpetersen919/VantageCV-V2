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

