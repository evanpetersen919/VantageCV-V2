# Pre-registration: do synthetic riders help real-image detection of riders, bikes and motors?

Registered 2026-10-09, before any rider asset is built, any rider image is rendered and any detector is trained for
this question. Changes after this point are allowed only as dated amendments at the bottom, never as edits to the rules
above them, and a result produced under a changed rule is labelled as such.

Each rule below is either **measured** (traced to a file in this repository), **recipe** (the project's existing,
logged training recipe) or **choice** (a decision made now, without evidence, and fixed so it cannot be tuned to
results). Choices are the weakest part of a pre-registration and are marked.

## 1. Question

Does adding synthetic images of riders on bicycles, motorcycles and scooters (Rocketbox riders on vehicles modelled
for this project, with exact engine labels) improve detection of `rider`, `bike` and `motor` on real BDD100K
validation images, **beyond what the same number of extra real rare-class images would give**?

The second half is the point. A gain over a real-only baseline can come from showing the detector any extra
rider-containing images; only a gain over matched real images is evidence about the synthetic data.

## 2. What is measured

- **Test set:** BDD100K detection validation, 10,000 images, **measured**: 649 rider, 1,007 bike, 452 motor instances
  (`docs/riders/bdd100k_rider_statistics.md`). The set is used for the final scoring only, once per arm and seed.
- **Classes:** `rider` (the person), `bike`, `motor` as BDD100K labels them; `person` and `car` as guards. Label
  convention for synthetic data: `rider` is the person's visible-part box, `bike` or `motor` is the vehicle's
  visible-part box, separate boxes, exactly as measured in BDD100K.
- **Prerequisite (not yet built):** the current evaluation code treats BDD `rider` as an ignore region for `person` and
  drops `bike` and `motor` (`src/evaluation/class_maps.py`). A loader and class map that score rider, bike and motor
  as classes must be written and tested first; the COCO-pretrained detector's `bicycle` (index 1) and `motorcycle`
  (index 3) outputs would map to `bike` and `motor`.
- **Metric:** AP@[.5:.95] per class with the project's evaluation settings (`--conf 0.001 --iou 0.6 --max-det 100`,
  image size 960), **recipe**.
- **Primary outcome M:** the mean of the three classes' AP, rider, bike and motor. One number per trained run.

## 3. Arms

All arms share one real base set and differ only in what is added. Total training steps and the training recipe are
identical across arms.

| Arm | Training images |
|---|---|
| A | Real base only |
| B | A + S **real** rare-class images (BDD100K training images that contain a rider, bike or motor, not in the base set) |
| C | A, with repeat-factor sampling (see below) instead of added images |
| E | A + S **synthetic** rare-class images |

- **Real base set:** 1,838 randomly drawn BDD100K training images, the size of the project's established real control
  (**recipe**, `bin/prepare_real_control.py`). By the measured rates it holds roughly 94 rider, 114 bike and 60
  motor images, so these classes are very scarce in it. A second regime with four times the real base is run only if
  E beats B in the first (to see whether the effect shrinks); it follows the same rules.
- **S = 1,000** (**choice**). S = 250 and 500 are run as an exploratory sweep and are not used for the decision.
- **B's extra images** are drawn at random (fixed seed) from the training images that contain at least one of the
  three classes; every image counts as one added image, as in E.
- **C: repeat-factor sampling** (LVIS), r_c = max(1, sqrt(t / f_c)) with f_c the share of base-set images containing
  class c, an image taking the largest r_c of its classes. **t = 9 x the smallest f_c in the base set** (**choice**),
  so the rarest class is repeated 3 times and the others about 2 to 3 times.
- A copy-paste arm (real rider crops pasted into other images) is **not** registered. It is added only if E beats B,
  as a further baseline, and is then labelled exploratory.

## 4. Fixed settings (all arms)

**Recipe:** YOLOv10m from scratch (`yolov10m.yaml`), 200 epochs, image size 960, batch 8, mosaic 1.0 with close-mosaic
10, and the optimizer fixed explicitly to AdamW with `--lr0 0.00125 --momentum 0.9 --warmup-bias-lr 0.0`
(`hpc/run_arm.sbatch`, `OPTIMIZER=AdamW`). The optimizer is set explicitly because ultralytics' `auto` picks a
different one depending on run length, which confounded earlier comparisons. **Seeds:** 0 to 4, **5 per arm**
(**choice**, motivated by evidence that 3 seeds understate the spread). One machine class for all arms.

## 5. Decision rule

Differences are computed per seed and paired by seed: d_s = M_E(s) - M_B(s), s = 0..4.

- **Synthetic data helps beyond real rare-class images** only if all hold:
  1. the mean of d_s is greater than 0;
  2. the 95% paired t-interval for the mean of d_s (4 degrees of freedom) excludes 0;
  3. a paired bootstrap over validation images (10,000 resamples; M recomputed for E and B, each averaged over the
     five seeds) gives a 95% interval for the difference that excludes 0;
  4. the guards hold: mean car AP and mean person AP of E are each no more than 1.0 AP below A's (**choice**).
- **Synthetic data hurts** if both intervals (2 and 3) lie entirely below 0.
- **Otherwise the result is inconclusive.** Inconclusive means the experiment could not tell, not that there is no
  effect, and it is reported as such.

Secondary, reported but not used for the decision: E against A and against C; AP for each class separately; AP by
box size (small is under 32 x 32 px) and by time of day; recall at fixed precision; the effect of S (250, 500,
1,000). The per-class table is reported for every arm so a gain that exists in only one class is visible. Where a
secondary comparison shows an effect, it is described as exploratory.

## 6. What the synthetic data must look like

The generator is matched to the measured BDD100K targets before any detector is trained, and the match is **reported
as a side-by-side table**, not gated on an arbitrary tolerance (a tolerance would be a choice made without
evidence). Targets, all **measured**: instances per image that contains the class (rider 1.26, bike 1.66, motor 1.31),
box height, width and aspect percentiles, bottom-edge and centre positions, truncation rates, the share of
unridden bike and motor boxes (65.2% and 63.7% at overlap 0.3; 58 to 72% over the thresholds), rider-vehicle pairing, and
the day, dusk and night mix. Lean, speed, lane position, clothing and helmets have no sourced target and are
varied, not matched; the report says so.

Hard defects are gated: a pose check that every hand touches a grip and every foot a pedal or footpeg, and an
automatic check of exact masks and boxes on every rendered image, with the failures counted and reported.

## 7. Reporting commitments

- Every arm, seed and class result is published in `results/` and `docs/experiments/`, including runs that fail the
  decision rule.
- A negative or inconclusive result is logged with the same detail as a positive one.
- The synthetic data is rendered with the plugin fix for the class-map depth tie (commit `f69e2e0`) and the labels
  are audited as for earlier batches.
- Vendor and paper figures quoted in `docs/riders/` are not used as targets or thresholds.

## 8. Limits stated in advance

- 649, 1,007 and 452 validation instances are few; per-class AP will be noisy and the bootstrap interval may be wide.
  A small true gain may well come out inconclusive.
- The real base is small by design, to be the regime where synthetic data could matter. A result there does not say
  what happens with all 70,000 real training images.
- Only the BDD100K label convention is the target. Other datasets disagree on who is a rider or a cyclist.
- Scooters, kick scooters and cargo bikes have no BDD class of their own; where BDD labels them is not measured here.

## Amendments

**2026-10-09, amendment 1 (no rule changed).** The evaluation prerequisite in section 2 now exists: a class profile
`RIDER_PROFILE` (person, bike, car, motor, bus, truck, rider; ids 1, 2, 3, 4, 6, 8, 10 with bike and motor on COCO's
bicycle and motorcycle ids) in `src/evaluation/class_maps.py`, used by the BDD100K and Cityscapes loaders, the scorer
and `bin/evaluate_detector.py --profile riders`. The default four-class behaviour is unchanged and its tests pass. A
cheaper study that needs no new assets, `headroom_check.md`, is registered to run first; it decides whether this
experiment is worth building towards. None of the rules above is altered.
