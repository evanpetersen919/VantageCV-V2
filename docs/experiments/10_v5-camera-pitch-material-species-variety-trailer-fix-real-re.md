## v5 — camera pitch + material/species variety + trailer fix (real re-render)

**Change:** a genuine full re-render (2,037 images, same seed/bounds/scenario count as v3 for
a controlled comparison), not a post-process of existing images like v4a/v4b were. Five
changes bundled into one render cycle (see the v5b entry above for the full detail and why
they were bundled rather than paid for separately): camera pitch jitter (+-3 deg, was
perfectly level every frame), sidewalk material varies per block (6 real variants, was 1
fixed material everywhere), building wall materials gained 5 unused-but-migrated variants,
tree species varies per scenario (Alder/Maple Red/Maple Sugar, was always birch), and a real
bug fix -- `vehTruck_trailer01` (a cab-less cargo trailer) is no longer sampled as a
standalone "truck" vehicle (was 1-in-4 truck spawns, driving down the road with nothing
pulling it). Training also switched to `mosaic=0` per v5a's own finding. Because five changes
landed in one render, **this result cannot attribute the gain to any single cause** -- that
would need separate, isolated re-renders per change, which the priority list already flags
as future work if it matters.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v4b → v5 | 3.6 / 7.5 → **4.0 / 8.7** (car 14.2→19.9, bus 1.4→2.1 up; person 12.1→11.2, truck 2.5→1.7 down) | 4.3 / 8.1 → **7.8 / 15.4** (car 19.9→32.5, bus 2.0→10.4, truck 1.3→7.0 — every class up, bus/truck roughly 5x) |
| Fine-tune v4b → v5 | 6.3 / 12.0 → **6.4 / 12.8** (person 13.3→14.4, car 25.4→27.6, bus 3.4→4.8 up; truck 6.0→4.5 down) | 12.4 / 20.4 → 12.0 / 22.4 (AP50 up, AP(.5:.95) flat/slightly down; person 22.7→24.5, car 39.3→45.0 up, bus flat, truck 6.2→7.2 up) |

**Verdict: the best single result in this log so far, especially the scratch-arm Cityscapes
jump (AP50 8.1→15.4, +90% relative, every class improving, bus/truck roughly 5x) — too large
to be pure noise given it's consistent across all four classes, though still an n=1 run per
the statistical-rigor gap flagged earlier.** BDD100K gains are real but more modest (+1.2 AP50
scratch, +0.8 AP50 fine-tune). Truck AP50 shows a small, consistent dip on BDD100K in both
arms (2.5→1.7, 6.0→4.5) — worth watching, but truck ground truth is a small class (4,231
BDD100K boxes) where the statistical-rigor agent already flagged 2-4x swings as
noise-consistent without repeated seeds. Net: this is real, meaningful progress, but per the
priority list's #1 finding (Grad-CAM's spurious-texture attention, unaddressed by any change
in this log so far), transfer is still far from the COCO-pretrained (34.8 AP) or real-control
(28.1 AP) baselines.

