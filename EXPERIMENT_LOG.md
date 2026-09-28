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

## v4b — modal occlusion boxes (planned)

Regenerate v3's annotations only (same images), shrinking occluded-object boxes to their
visible region using the occlusion ray-cast data already computed at generation time, instead
of keeping full un-occluded extent above the 0.5 visibility floor. Confirmed via BDD100K's
official annotation instructions (direct quote) that real ground truth boxes only the visible
portion for both truncation and occlusion — this is an independent, separately-evidenced
hypothesis from v4a's pixel-realism one, tested in isolation here for the same reason.

## Not yet scheduled

Mosaic/augmentation ablation, tree-species variety — cheap but lower expected impact,
deprioritized behind v4b.
