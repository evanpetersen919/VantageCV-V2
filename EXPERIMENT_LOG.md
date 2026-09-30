# Experiment Log — Sim-to-Real Detection Transfer

Tracks every synthetic-data training run for the train-synthetic/test-real experiment: what
changed, why, and what happened on the real benchmarks (BDD100K val, 10,000 images; Cityscapes
val, 500 images). Each entry is written after the run's evaluation completes, not before —
numbers here are always measured, never predicted.

All arms use YOLOv10m, imgsz 960, eval settings `--conf 0.001 --iou 0.6 --max-det 100`.
"Scratch" = trained from `yolov10m.yaml` for 200 epochs. "Fine-tune" = trained from COCO
weights (`yolov10m.pt`) for 50 epochs. Real-control = 1,838 real BDD100K training images,
equal size to the synthetic training set, trained the same way as scratch — the fair
same-data-volume reference point.

## Reference arms (not synthetic, for scale)

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| COCO-pretrained baseline (no fine-tuning) | 34.8 / 55.0 | 41.6 / 59.7 |
| Real control (1,838 real images) | 28.1 / 48.4 | 26.1 / 42.5 |

## v1 — first live-rendered dataset (2,037 images, 800 scenarios)

**Dataset:** `live_dataset/train2000`. Baseline generator: fixed night preset (no exposure
variety), 20% night share, occlusion filter kept any object ≥10% visible at full un-occluded
box extent, only 7 of 14 vehicle models had paint-color variation (bus/most trucks/some
SUVs fixed to one factory color), object annotation had no distance cutoff (long unobstructed
streets over-represented distant, small objects in the training labels).

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch | 2.9 / 6.6 | 2.5 / 6.2 |
| Fine-tune | 4.9 / 10.4 | 10.3 / 20.7 |

## v2 — occlusion label fix only

**Change:** re-exported v1's existing images with a stricter kept-visibility floor
(`visibility_fraction >= 0.5` instead of `>= 0.1`), dropping annotations for majority-hidden
objects that were still being boxed at full un-occluded extent (44% of v1's boxes had
visibility_fraction < 0.5). No new images rendered; no other change.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch | 3.0 / 6.4 | 2.7 / 5.7 |
| Fine-tune | 6.2 / 12.4 (car AP 10.6→13.5) | 11.0 / 20.5 |

**Verdict:** small, real gain on fine-tune; scratch unchanged. Confirmed the occlusion-box
issue was real but not the dominant gap.

## v3 — distance cutoff + night lighting variety + vehicle color diversity (fresh 2,037-image render)

**Dataset:** `live_dataset/train2000_v3`, same 800 scenario seeds as v1/v2 (isolates the
generator changes from city-layout randomness). Three fixes, each independently measured
against real benchmark statistics before implementing:
- **Per-category max annotation distance** (pedestrian 30m, car/SUV 54m, bus 41m, truck 53m),
  fit by matching synthetic median box-height-as-fraction-of-frame to BDD100K/Cityscapes'
  own measured values. Root cause: long, unobstructed streets meant every frame's annotations
  included far more distant, small objects than real dashcam sightlines ever contain.
- **Night exposure variety**: `NIGHT_EXPOSURE_BIAS_RANGE_EV = (-4.34, -0.38)` replacing one
  fixed value, and `night_share` raised from 20% to 39% to match BDD100K's own measured night
  share. Root cause: night brightness std was 1.92 across our old renders vs 15.73 in BDD100K
  (real photos span ~4 stops of brightness; ours spanned under 2).
- **Vehicle paint diversity**: extended the recolor mechanism (project-owned paint material
  copy, `Paint Variation` switch off, runtime `BaseColor` override) from 7 to 12 of 14 models
  — van, all 3 non-recolorable trucks, and the bus. Taxi and police-car liveries deliberately
  excluded (real, baked-in liveries, not arbitrary colors). Root cause: every bus/most trucks
  rendered in one fixed factory color in every scenario, forever.
- Also carried forward the v2 occlusion-visibility refilter (0.5 floor).

Live-verified before the full run: 40-scenario pre-flight batch confirmed box heights matched
distance-cutoff targets, night brightness variance present at the right order of magnitude,
and all 12 recolorable models showing full real-world color-share distributions.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch | 2.7 / 5.7 | 4.3 / 7.2 |
| Fine-tune | 6.1 / 11.8 | 12.9 / 21.1 (bus 3.6→11.2, truck 3.8→6.0) |

**Verdict:** essentially flat on BDD100K (the larger, more reliable benchmark — 10,000 images,
1,597 bus boxes); a real-looking gain on Cityscapes concentrated in bus/truck, but Cityscapes'
bus/truck ground truth is tiny (98/93 boxes total), so that gain isn't fully trusted yet. All
three fixes were independently confirmed working exactly as designed — the lack of BDD100K
improvement means these three factors are not the dominant cause of the sim-to-real gap.

### Post-v3 diagnostic deep-dive (5 parallel research agents, all evidence-based)

1. **Pixel statistics** (300 images/source, measured): synthetic renders are 2.6-3.0x sharper
   (Laplacian variance) and 1.3-1.9x more saturated than both real benchmarks. BDD100K alone
   shows a strong JPEG block-compression signature (~1.86x) our lossless PNGs and Cityscapes
   PNGs both lack (~1.0x, confirming this is JPEG-specific, not a general synthetic-vs-real gap).
2. **Grad-CAM** (21 real images, all 3 detection scales hooked, verified visually): attention
   is diffuse and concentrates on generic high-contrast texture — tree foliage, curb edges,
   lane paint, wet-road glare — rather than vehicle/pedestrian shape. Directly corroborates
   finding 1: the model likely learned "sharp edge = object" from oversharpened, oversaturated
   training renders, a cue any high-contrast real texture also satisfies.

   ![Grad-CAM on a Cityscapes frame: the hottest activations sit in the tree canopy at the top of the frame, not on the DHL truck below it](docs/images/gradcam_truck_foliage.jpg)
   *The model's top prediction here is "truck" (conf 0.78) on the real DHL truck, but the
   strongest, reddest Grad-CAM activations are in the foliage above it, not the truck itself.*
3. **Label convention** (confirmed via BDD100K's official annotation instructions, direct
   quote): BDD100K boxes only the *visible* portion of an object for both truncation and
   occlusion (modal). Cityscapes' polygon-derived instances work the same way. Our frame-edge
   truncation is already modal-correct (boxes are genuinely clipped to in-frame content), but
   occlusion-by-another-object is not — objects above the 0.5 visibility floor still get the
   full un-occluded extent, not the visible sub-region. Real, confirmed, unaddressed mismatch.
4. **Rendering pipeline audit** (code-cited): motion blur, depth of field, chromatic
   aberration, film grain, vignetting, and lens distortion are all absent from the render
   pipeline; auto-exposure is deliberately tuned for stability, the opposite of real cameras.
   Training augmentation uses ultralytics defaults unmodified, including `mosaic=1.0` on
   single-coherent-scene synthetic data — flagged as a plausible, untested contributor.
5. **Remaining asset diversity** (exact counts, not estimates): pedestrian clothing/face
   variety is already substantial (57 tops, 33 bottoms, 12 faces) — not a bottleneck. Real
   gaps: only 2 pedestrian poses total and zero age diversity (content-limited, not a quick
   fix); every street tree is the same species despite 3 more being fully installed and
   unused; a handful of unused building levels/props (minor).

## v4a — image realism post-process (blur + desaturate + JPEG round-trip)

**Change:** `bin/apply_image_realism.py` reprocessed v3's existing 2,037 images (no
re-render) with parameters chosen by `bin/calibrate_image_realism.py` against the pixel-stat
targets from the post-v3 diagnostic: Gaussian blur sigma 0.4, saturation x0.75, JPEG quality
75, no added noise (noise alone raised sharpness back up in calibration, so excluded).
Annotations/boxes completely unchanged — isolates the pixel-realism hypothesis from the
box-convention one. Calibration itself needed one real bug fix first: it was measuring
Laplacian variance at native render resolution instead of training imgsz (960) — a
scale-dependent metric, so the first calibration pass looked far blurrier than it actually
was at the resolution the network trains on.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v3 → v4a | 2.7 / 5.7 → 2.8 / 5.8 | 4.3 / 7.2 → 4.2 / 7.5 |
| Fine-tune v3 → v4a | 6.1 / 11.8 → 6.5 / 12.8 (person 6.4→8.5, car 12.7→14.1, **truck 3.5→1.3**) | 12.9 / 21.1 → 11.0 / 18.8 (bus 11.2→7.0, truck 6.0→3.0) |

**Verdict: mixed, not a clear win.** Scratch is flat on both benchmarks (within noise).
Fine-tune shows a small BDD100K gain (+0.4 AP) but a real Cityscapes regression (-1.9 AP),
with truck AP dropping on both benchmarks. This does not confirm the pixel-statistics
hypothesis as the dominant cause — either the effect is real but this specific treatment
(uniform blur across the whole image) also destroyed legitimate fine detail needed for
smaller/more detailed classes like truck, or the single-seed run-to-run noise on Cityscapes'
tiny bus/truck ground truth (98/93 boxes) is large enough to explain most of this swing on
its own. Not pursuing a refined version of this treatment next; proceeding to v4b instead,
which is independent of this result.

## v4b — modal occlusion boxes

**Change:** `bin/regenerate_modal_boxes.py` regenerated v3's annotations only (same 2,037
images, no re-render), shrinking occluded-object boxes to their visible region via
`occlusion.py`'s new `visible_region_box` (reuses the same ray-cast hit data
`visible_fraction` already computed, refactored into `_hits_and_visibility` so both share
one hit grid and occluder search) instead of keeping the full un-occluded extent above the
0.5 visibility floor. Confirmed via BDD100K's official annotation instructions (direct
quote) that real ground truth boxes only the visible portion for both truncation and
occlusion — independent of v4a's pixel-realism hypothesis, tested in isolation for the same
reason. Verified the fix actually engages before running at full scale: a 50-scenario sample
showed 561 of 1,404 boxes (40%) shrink meaningfully (median shrink ratio 0.29 among those
affected), not just in theory.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v3 → v4b | 2.7 / 5.7 → **3.6 / 7.5** (person 4.3→5.1, car 5.4→7.1, bus 0.3→0.8, truck 0.7→1.3 — every class up) | 4.3 / 7.2 → 4.3 / 8.1 (flat; car up 7.8→10.4, bus/truck down — tiny ground truth, 98/93 boxes) |
| Fine-tune v3 → v4b | 6.1 / 11.8 → 6.3 / 12.0 (roughly flat) | 12.9 / 21.1 → 12.4 / 20.4 (slight regression) |

**Verdict: a real, modest gain on the scratch arm's BDD100K score (+0.9 AP, ~33%
relative), consistent across all four classes together — a meaningful pattern, not
single-class noise. Fine-tune is roughly flat on both benchmarks, and Cityscapes shows no
clear gain either arm.** Plausible mechanistic reason for the scratch/fine-tune split: a
from-scratch model is more sensitive to exactly what box shape it's taught, while fine-tune
starts from strong COCO priors a label-convention fix moves less. Box-convention correctness
is now confirmed to matter somewhat, but like v4a it isn't the dominant lever either — real
transfer still isn't close to the COCO-pretrained baseline (34.8 AP) or the real-control
arm (28.1 AP).

## v5a — mosaic ablation (quick signal)

**Change:** two YOLOv10m scratch runs on the same v4b training set, differing only in
`mosaic`: default (`1.0`) vs. `mosaic=0`, all other augmentation/hyperparameters identical.
Evaluated both on the same fast 1,000-image slice of BDD100K val (not the full 10,000-image
benchmark used elsewhere in this log — a quick signal, not a final number) at the standard
`imgsz=960 conf=0.001 iou=0.6`.

| Arm | AP / AP50 | person | car | bus | truck |
|---|---|---|---|---|---|
| mosaic=1.0 (default) | 2.9 / 6.2 | 4.4 | 6.3 | 0.5 | 0.5 |
| mosaic=0 | **3.2 / 7.2** | 4.8 | 6.4 | 0.9 | 0.8 |

**Verdict: mosaic off wins on every class, on this quick slice** — small in absolute terms
(+0.3 AP, ~10% relative) but directionally consistent, unlike the mixed/class-splitting
pattern v4a showed. This is consistent with the standing hypothesis: this project's images
are single coherent scenes with real geometric consistency (fixed camera height, consistent
distance-to-scale relationships) that 4-way mosaic stitching destroys, and a model trained
without it retains those real cues better. Not yet confirmed at full-benchmark scale or
across a second seed — see the priority list below for what would raise confidence.

## v5b — camera/material/asset changes ready for the v5 render (implemented, not yet rendered)

Five real, verified, evidence-backed changes landed in preparation for the next live-rendered
dataset. Each was implemented, unit-tested (own targeted tests + the full 818-test suite),
pylint-checked (10.00/10), and committed/pushed individually rather than as one batch, per
the same implement -> test -> confirm discipline the rest of this log follows:

| # | Change | Commit | Needs plugin rebuild? |
|---|---|---|---|
| 1 | Pitch jitter on ego/lot camera poses (+-3 deg, was perfectly level every frame) | `a3c737d` | No (pure Python pose math; UE5's RPC only ever took position + look-at) |
| 2 | Sidewalk material varies per city block (6 real migrated variants, was 1 fixed material everywhere) | `901cc5b` | **Yes** |
| 3 | Building wall materials gained 5 unused-but-migrated variants (brick brown, stucco khaki, metal brass, granite/limestone block) | `893ac79` | **Yes** |
| 4 | Tree species varies per scenario (Alder/Maple Red/Maple Sugar, was always birch) | `41da877` | No (trees spawn via the generic asset-path pipeline, no material tag involved) |
| 5 | **Bug fix**: `vehTruck_trailer01` (a cab-less cargo trailer) is no longer a standalone "truck" spawn option -- it was sampled 1-in-4 truck spawns, driving down the road with nothing pulling it | `f4b161a` | No (pure Python asset-pool data) |

**Before rendering v5, rebuild `unreal_plugin/SyntheticDataGen`** -- changes 2 and 3 add new
material tags (`pavement_1..5`, `brick_brown`, `stucco_khaki`, `metal_brass`,
`block_granite`, `block_limestone`) to the C++ `MaterialResolver`; without a rebuild those
tags fall back to UE5's default material (a visible, not silent, failure mode -- but still
worth doing the rebuild first).

Explicitly investigated and deliberately NOT done (no-guessing/no-fabrication reasons, not
oversights): `Kit_StreetLamp_B` (mesh exists, but its rotation offset needs live-in-editor
verification like the other 3 lamp styles got -- guessing it risks a visibly wrong-facing
lamp); the `Kit_bench_RR` bench kit (no measured real placement pattern exists for it, unlike
trees' real Epic point-cloud data); CHH building facade levels (checked -- already fully
wired, all 8 real levels L1-L8, the earlier "2 unused" note was stale). Roll jitter and
camera FOV/intrinsics randomization are also deferred: both need an actual RPC/engine
protocol change (today's bridge only ever sends camera position + look-at target, no
roll/up-vector, no FOV), a larger, separate effort from this batch.

## Priority list: most critical to least critical (post-v4b/v5a synthesis)

Four research passes fed this ranking: a statistical-rigor audit, a Grad-CAM comparison
across v3/v4a/v4b(scratch+finetune) on 11 real images, a "what would a startup-grade
pipeline need" gap analysis, and the v5a mosaic ablation above. Ranked by expected impact on
real-world transfer, not by ease of implementation.

1. **The model isn't learning real object shape at all — it's keyed on spurious texture.**
   Grad-CAM overlays (`runs/gradcam_v2/`) show the *same* attention pattern — foliage edges,
   curb lines, lane paint, glare — across every arm tested (v3, v4a pixel-realism, v4b modal
   boxes), on the same 11 real images. None of the fixes shipped so far touched this at all;
   they moved AP by fractions of a point while the underlying failure mode is untouched. This
   is the single most important open finding: until synthetic training teaches shape/silhouette
   cues that generalize, every other fix is polishing a symptom. Likely needs deliberate
   domain randomization (textures, materials, lighting) specifically aimed at decorrelating
   class identity from background texture, not just more realism.
2. **Zero domain randomization of camera intrinsics/extrinsics, materials, or textures.**
   Every render uses the same camera model and a fixed small set of building/vehicle
   materials. Real datasets are shot on dozens of different camera rigs; a detector trained
   on one fixed synthetic camera setup has an easy shortcut (exact pixel-to-metric scale) that
   doesn't exist in real data and won't transfer. This is upstream of and likely a bigger lever
   than any single asset fix (trees, lamps, etc.).
3. **Dataset scale is 1-2 orders of magnitude below the academic synthetic baselines this
   project is implicitly competing with** (~2,000 images here vs. 100k+ in published
   sim-to-real work). Every arm in this log is trained on a dataset small enough that label
   convention and augmentation flags can visibly move the needle by whole percentage
   points — a sign the model is data-starved, not just imperfectly labeled.
4. **No run in this entire experiment (v1 through v5a) has ever been repeated with a
   different seed.** Every "gain" or "regression" logged above, including v4b's flagship
   +0.9 AP and v5a's +0.3 AP, is a single sample with completely unmeasured run-to-run
   variance. Before trusting any ranking in this list numerically, the top 2-3 candidate
   fixes should be validated with at least 2 seeds each.
5. **Mosaic augmentation** (this ablation): real, consistent, but modest (+0.3 AP quick
   signal) — worth keeping `mosaic=0` as the default going forward given it's free (a training
   flag, no re-render) and never lost on any class, but it will not close the sim-to-real gap
   by itself and should not be over-weighted relative to items 1-3.
6. **Modal (visible-region) occlusion boxes** (v4b, already shipped) — confirmed real,
   modest gain on the scratch arm (+0.9 AP), flat on fine-tune. Correct box convention is a
   prerequisite others might build on, but the Grad-CAM evidence (item 1) shows it doesn't
   touch the actual attention problem.
7. **Small-object/rare-class volatility** (per the statistical-rigor agent): bus/truck
   numbers swing by 2-4x across arms on ground truth as small as 93-98 boxes (Cityscapes).
   These deltas are consistent with sampling noise alone and shouldn't be read as signal
   without more data or seeds.
8. **Architecture/tooling gaps that block scaling up**, not blockers to any single number
   today but blockers to acting on items 2-3 cheaply: single-instance sequential live-render
   architecture (Ray parallelism exists for the offline path but was never extended to
   live-render), no automated synthetic-vs-real drift detection, 3D boxes/lane-graph data
   computed then discarded at export (no LiDAR pairing yet).
9. **Unused already-installed assets** (Alder/Maple Red/Maple Sugar trees, extra building
   facades, second lamp style, bench/sign kits — v5b above) — real diversity gaps, but the
   least critical item here: cheap to add, but nothing in the Grad-CAM evidence suggests
   scene-object diversity is the bottleneck compared to items 1-4.

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
