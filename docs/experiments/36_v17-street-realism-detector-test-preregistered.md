## v17 street realism: does it change detector AP? (pre-registered 2026-10-10; result 2026-10-10: no resolvable effect)

Written before the render finishes and before any detector is trained on it. Result: **no resolvable effect** (see Result below).

**Question.** Entries 30 to 34 made the streets look more like real ones (lane markings and stop lines, signal heads that
follow the phase, wet-road-capable scenes unchanged, scanned trees, shrubs and grass). None of that has been tested against a
detector. Does a detector trained with real BDD100K images plus the v17 synthetic supplement score differently on real
BDD100K validation images than the same detector with the v13r supplement?

**Arms (same scenes, same seeds).**

| Arm | Synthetic supplement | Config |
|---|---|---|
| `v13r25` (existing) | `train_v13r`: seeds 70000 to 70255, 512 frames, exact labels | `urban_dense_v13r.yaml` |
| `v17_25` (new) | `train_v17`: the same seeds 70000 to 70255, 512 frames, exact labels | `urban_dense_v17.yaml` |

Both use the 25% real regime of the project's logged recipe (YOLOv10m from scratch, 200 epochs, 960 px, AdamW fixed, seeds
0, 1, 2) and are scored with the same settings on BDD100K val and Cityscapes val. Because the layout, traffic and
pedestrians for a seed are unchanged by the v14 to v17 flags (a tested property), the differences between the arms are the
street-level features only: markings and stop lines (and the queue position with them), signal heads, trees, shrubs, grass.
The v17 vegetation also changes in spring and summer (none before), which is part of what is being tested.

**What is not controlled.** These changes are bundled, so a difference cannot be attributed to one of them. This is a
"does the bundle matter" test, not an ablation.

**Primary outcome.** Overall BDD100K AP@[.5:.95] (person, car, bus, truck), mean over three seeds, v17_25 minus v13r25.

**Decision rule (fixed now).**
- **Helps**: mean difference at least +0.5 AP and a paired comparison over seeds that is positive in all three.
- **Hurts**: mean difference at most -0.5 AP and negative in all three.
- **No resolvable effect**: otherwise (the project does not interpret differences under about 0.5 AP at three seeds).

Reported, not decisive: per-class AP, Cityscapes AP, AP by time of day, and the person, car and truck guards.

**Limits stated in advance.**
- Three seeds, one real-data size, one batch size: a null result is "not resolvable", not "no effect".
- v13r and v17 differ in vegetation for spring and summer scenes, in winter and fall the trees are different models.
- The synthetic supplement is 512 images; effects of road paint on small boxes may need more.

**Run.** Render `live_dataset/train_v17` (`bin/generate_live_dataset.py --profile v7 --config ...v17.yaml
--num-scenarios 256 --seed 70000 --exact-labels`), split by scenario, upload with the cluster scripts, three seeds.

## Result (2026-10-10)

Rendered as registered: `train_v17`, 256 scenarios, seeds 70000 to 70255, 512 frames, calibration 0.51 px, no rejected
frames; split by scenario exactly as `train_v13r` (230 train and 26 validation scenarios, same time-of-day and weather
counts). Trained and scored with the same recipe (`hpc_v17_25_s0` to `s2`, three seeds, 25% real, AdamW, 200 epochs,
960 px) and scored on BDD100K val (10,000 images) and Cityscapes val. Mean over three seeds, AP@[.5:.95] in percent:

| BDD100K val | v13r25 | v17_25 | v17 - v13r | per seed (0, 1, 2) |
|---|---|---|---|---|
| **overall (primary)** | 21.20 | 21.36 | **+0.15** | +0.09, +0.17, +0.21 |
| person | 16.95 | 16.92 | -0.02 | -0.16, -0.37, +0.45 |
| car | 38.55 | 38.49 | -0.06 | +0.12, -0.16, -0.15 |
| bus | 13.47 | 14.37 | +0.90 | -0.06, +1.36, +1.41 |
| truck | 15.85 | 15.65 | -0.20 | +0.44, -0.16, -0.87 |

| Cityscapes val | v13r25 | v17_25 | v17 - v13r | per seed (0, 1, 2) |
|---|---|---|---|---|
| overall | 22.21 | 22.87 | +0.66 | +0.55, +1.56, -0.13 |
| person | 15.40 | 15.40 | +0.00 | -1.49, +0.39, +1.10 |
| car | 38.13 | 38.69 | +0.56 | +0.70, +0.48, +0.49 |
| bus | 21.23 | 22.52 | +1.29 | +1.99, +3.84, -1.95 |
| truck | 14.07 | 14.87 | +0.79 | +1.02, +1.52, -0.16 |

**Against the rule.** The primary outcome's mean difference is +0.15 AP, below the +0.5 needed for "helps". It is
positive in all three seeds, but the size is under what the project resolves with three seeds, so the registered verdict
is **no resolvable effect**. It is neither "helps" nor "no effect": the direction is consistently positive and small.

**Reported, not decisive.**
- Cityscapes overall is +0.66 but negative in one seed (-0.13), so it would not meet the "helps" rule either; the
  Cityscapes gain is carried by car (+0.56, positive in all three seeds) and by the noisy bus and truck classes.
- Bus and truck move by more than 0.5 in places (bus +0.90 on BDD100K, +1.29 on Cityscapes) but the per-seed spread
  (bus -1.95 to +3.84 on Cityscapes) is larger than the effect; with 1,597 bus boxes on BDD100K val these are not
  readings of the street features.
- The guards hold: person and car are within 0.1 AP of v13r25 on BDD100K.

**What it means for the project.** Making the streets look more like real ones (markings, signals, scanned trees,
shrubs, lawn) did not hurt the detector and did not measurably help it at this sample size. Visual realism of this kind is
therefore not, by itself, where detector transfer is gained or lost; the rider study (class coverage, not looks) is the
better lever. The limits stated above stand: three seeds, one data size, a bundled change.

Files: `results/hpc_v17_25_s{0,1,2}_{bdd100k,cityscapes}.json`.
