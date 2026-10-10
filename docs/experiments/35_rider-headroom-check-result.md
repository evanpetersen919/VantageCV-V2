## Rider headroom check: more real rider images help a lot (2026-10-10)

The check registered in `docs/riders/headroom_check.md` (2026-10-09, before any of these runs) asked whether, at the
project's real-data size of 1,838 images, adding real images of riders, bikes and motors raises rider, bike and motor AP
on real BDD100K validation images beyond what the same number of ordinary real images does. The 15 cluster runs
(5 arms x seeds 0, 1, 2; YOLOv10m from scratch, 200 epochs, AdamW, 960 px) finished and were scored with the rider
profile. The rule was applied by `bin/analyze_rider_headroom.py` (tested), exactly as registered.

**Result: headroom exists.** M is the mean AP@[.5:.95] of rider, bike and motor on BDD100K val (10,000 images), in AP
points.

| Arm (training images) | Seed 0 | Seed 1 | Seed 2 | Mean |
|---|---|---|---|---|
| A: base, 1,838 | 7.22 | 5.86 | 7.15 | 6.74 |
| rand2: A + 172 random | 8.47 | 7.53 | 8.74 | 8.25 |
| rand4: A + 516 random | 7.88 | 8.08 | 9.23 | 8.40 |
| rare2: A + 172 rare | 10.03 | 10.89 | 10.77 | 10.56 |
| **rare4: A + 516 rare** | **14.41** | **14.68** | **14.65** | **14.58** |

Decision quantity d_rare = M(rare4) - M(rand4): **+6.54, +6.60, +5.42; mean +6.19**. The registered bar was a mean of at
least 1.0 and a positive value in all three seeds; both hold by a wide margin. Reported, not decisive:

- More images alone (rand4 - A): +0.65, +2.22, +2.09 (mean +1.65). Rare images are worth about 3.7 times as much.
- Doubling (rare2 - rand2): +1.55, +3.36, +2.03 (mean +2.31).
- Per class, rare4 against A (AP points): rider 7.1 to 15.7, bike 8.9 to 16.9, motor 4.2 to 11.1.
- **Guards**: car AP is +0.9 and person AP +3.6 for rare4 against A (rand4: +0.9 and +1.6), so the gain is not paid for
  by the common classes; if anything rare images help people.

**What it means.** At this data size a detector is starved of riders, bikes and motors, and the real rare images that
fix it are not available in quantity in a small real set. That is the argument for a synthetic supplement, and the
registered next step is the synthetic experiment in `docs/riders/preregistration.md`. This result does not say synthetic
riders will help: it says the headroom a synthetic supplement would have to fill is large (about 6 AP at 3x the rare
images), and sets the bar a synthetic arm must be compared with.

**Limits** (stated before the runs and still true): three seeds; rare images are chosen by label content and may be
easier or harder than the base set's riders; one real-data size (a flat curve at 70,000 images is possible); real rare
images carry real labels and noise, synthetic ones carry exact labels.

Files: `results/hpc_rider_<arm>_s<seed>_{bdd100k,cityscapes}_riders.json` (30), `results/rider_headroom_analysis.json`.
The Cityscapes files were scored but are not part of the registered decision.
