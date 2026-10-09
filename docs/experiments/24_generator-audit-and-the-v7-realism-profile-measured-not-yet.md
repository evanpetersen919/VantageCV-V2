## Generator audit and the v7 realism profile (measured, not yet trained)

Six read-only audits (assets, label definitions, lighting/camera, scene layout, throughput,
literature) compared the generator with BDD100K and with the measured cluster results. What was
found, what was fixed behind a `--profile v7` switch (the default `v6` is unchanged), and how each
fix was checked. Real-data numbers are from 10,000 BDD100K val labels and 1,838 control training
labels; synthetic numbers are from the v5/v5b sets and from probe renders.

**A label bug, found by measurement.** BDD100K's instructions box only the visible part of a
partly hidden object. `occlusion.filter_occluded` shrinks boxes that way, but
`mesh_labels.refine_with_meshes` runs afterwards and replaces every vehicle and pedestrian box
with the extent of its whole projected mesh, so **every dataset made so far has full-extent
boxes**. Evidence: in v5, 0 of 4,000 boxes are smaller than their own mesh hull; v4b differs from
v3 in 25 of 24,573 boxes (0.1%) and 93.8% are identical; the share of boxes overlapping another at
IoU > 0.3 is 8.0% in real control labels and 32.9% in v5. **This corrects the v4b entry above:**
v4b's labels were essentially v3's, so its logged "+0.9 AP from modal boxes" was seed noise (the
"561 of 1,404 boxes shrink" figure was measured on the intermediate step, before the overwrite).
Fix: a `modal` switch (`tight_box_2d`, `refine_with_meshes`, `render_frame`); a box and its
silhouette are cut to the visible region, truncation still counts only the part outside the image.
On the same 60 scenarios (ego views, seeds 60000+) the overlapping share falls from **18.8% to
4.5%** with it (real: 6.8-8.0%). Six unit tests. v7 turns it on; `bin/regenerate_modal_boxes.py`
(now with `--amodal`/`--limit` for checking) can regenerate old datasets' labels without
rendering; regenerating v5 in amodal mode reproduced the original boxes to 0.1 px on 14 images.

![The same frame labelled with full-extent boxes (left, every dataset so far) and visible-part boxes (right)](../images/labels_full_extent_vs_visible.jpg)

*Same frame, same scene. Left: every vehicle's whole extent, so the boxes behind the parked police car stack on top of each other. Right: the fixed labels follow what is visible.*

**Other measured generator differences and the v7 changes.**

| Item | v6 / v5 measured | Real | v7 change | v7 probe result |
|---|---|---|---|---|
| Truck share of boxes | 17.8% (pickups counted as trucks) | 3.3-3.5% | pickup counted as a car; per-model weights from the cited US registration shares; truck 4%, bus 1.5% of vehicles; taxi/police rare | 3.8% / 4.0%; 0.39-0.42 trucks per image (real 0.42) |
| Parking-lot view | 22% of images, 51% of trucks, 72% of its boxes overlapping | - | ego views only | - |
| Frames with a person | 94% of ego frames | 32% (44% city) | per-scenario density, `0.45 * u^3` | 37.5-40% (3+ persons: 18-23%; real 15-23%); persons per image 1.1 (real 1.33) |
| Night | blue-hour sky (top luminance 48 vs 24; blue/red 2.03 vs 0.87); auto-exposure lifts any dark scene | - | manual exposure +9.6 EV centre, dim cool moon, cool grade | saturation 0.32 (real 0.32), blue/red 0.77 (0.89); luminance re-centred +0.6 EV after the first probe read 19 vs 30 |
| Fog | start distance 300 m, past the whole scene: fog frames identical to clear; 7% of days | 0.1% | start at 0 m; 1% of days | not checked visually |
| Weather mix | clear .35, rain .15, fog .07 ... | clear .34, overcast .20, rain .075, snow .08 (not generated) | shares moved toward measured | - |
| Roads wet in clear weather | v6's always-on roughness jitter | - | jitter off in v7 | clear-day roads look dry in probe frames |
| Camera | pitch +-3 deg, height 1.4-1.9 m (horizon-row spread 0.024) | 0.105 | pitch +-7 deg, height 1.25-2.0 m | pitch spread 4.1 deg (about 0.056); still short of 0.105 |
| Hood | none | present in many frames | painted on a random half, 5-12% of height; boxes cut to the visible area | 52% of frames |

Not changed, and why: field of view (106 degrees horizontal against about 60 for a dash cam; it
changes how labels project, so it is a separate test); roll and ego headlights (need C++);
snow; the box-overlap share of the v7 ego frames is still 23% *without* the modal fix (4.5% with
it, on v6 scenes). The semi-truck (the cab `vehicle08` has a trailer socket and `vehicle08` plus
`vehicle01`... see the asset audit) is Tier B.

![A night frame from the previous generator (saturated blue sky), a v7 probe night frame (black sky, hood), and a real BDD100K night frame](../images/night_previous_v7_real.jpg)

*One randomly picked night frame each (not selected to flatter). The real frame happens to be a highway, which is 25% of BDD100K; the generator has no highways yet.*

**Withdrawn or corrected during this work:** the "unused livery variants" (the numbered material
instances are per-part materials); an interim claim that modal boxes were never integrated (they
are called, but then overwritten); an agent claim that the wet-road look came from the jitter for
v5 data (v5 predates the jitter; the jitter does explain v6/v7-code frames).

**Tools added:** `bin/measure_layout.py` (class shares, pedestrian presence, overlap, camera
spread, offline, about 4 s per scenario), `bin/compare_image_stats.py` and
`bin/calibrate_night.py` (image statistics against BDD100K, lighting calibration over candidates).

**Next:** (1) a label-only cluster test: the existing v5 images with regenerated visible-part
labels vs the original labels, same recipe and seeds (25% and 100% real); (2) the v7 batch (510
images), compared with `hpc_rand25` (same size, v5 images) at 25% real.

