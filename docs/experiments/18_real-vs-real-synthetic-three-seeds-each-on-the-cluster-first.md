## Real vs real + synthetic, three seeds each, on the cluster — first statistically supported gain, small and class-specific

**Change:** the comparison from the previous entry, repeated three times per arm on the college
HPC cluster so every number shares hardware and library versions (8x RTX A5500 node, Python
3.12.3, torch 2.14.0+cu130, ultralytics 8.4.163; local runs used an RTX 4080 and torch +cu126, so
cluster and local numbers are not directly comparable and are never mixed below). Real-only =
1,838 real BDD100K training images; mixed = those plus the 1,838 v5 synthetic images. Recipe
identical to the real-control run (scratch, 200 epochs, imgsz 960, batch 8, mosaic on,
`close_mosaic` 10), seeds 0/1/2, scored on BDD100K val (10,000) and Cityscapes val (500). Jobs
135697-135702. All 12 result files were checked for identical evaluation settings and
benchmark ground-truth counts to the local runs.

| Arm (mean ± sd over 3 seeds) | BDD100K AP | BDD100K AP50 | Cityscapes AP | Cityscapes AP50 |
|---|---|---|---|---|
| Real only | 28.28 ± 0.11 | 48.68 ± 0.30 | 26.35 ± 0.83 | 43.33 ± 1.04 |
| Real + synthetic | **28.94 ± 0.28** | **49.52 ± 0.38** | 27.52 ± 1.35 | 45.20 ± 1.63 |
| Difference (95% CI) | **+0.66 (+0.05 to +1.27)** | +0.84 (+0.05 to +1.64) | +1.17 (-1.60 to +3.94) | +1.87 (-1.45 to +5.19) |

Per-seed BDD100K AP: real-only 28.35 / 28.35 / 28.15; mixed 28.63 / 28.99 / 29.20 -- **every
mixed run beats every real-only run.** Welch p = 0.042 (the smallest possible exact
permutation p for 3 vs 3 runs is 0.05, which this reaches). Cityscapes is not significant
(500 images, larger spread).

By class (AP, mean over seeds, real-only → mixed): **person 21.4 → 23.3 (+1.9, p = 0.007)**
and **car 43.4 → 44.0 (+0.6, p = 0.001)** on BDD100K, and person 18.0 → 20.1 (+2.1) and car
42.2 → 43.9 (+1.7) on Cityscapes -- significant on both benchmarks. Bus and truck did not
change on either (BDD100K bus +0.1, truck +0.0). By condition: daytime +0.9 (p = 0.035), snowy
+1.6 (p = 0.038), rainy +1.2 (p = 0.061), clear +0.6, overcast +0.5; **night +0.2 (no effect).**

**Verdict: synthetic data adds a small but real amount when combined with real data -- about
+0.7 AP (2.3%) overall on BDD100K, concentrated in the person and car classes -- the first gain in
this log that survives repeated seeds.** What it does not show: any benefit for bus/truck or
at night; a statistically clear gain on Cityscapes; or that the images are worth more than
simply more data. Caveats, stated plainly: three seeds per arm (so p-values are rough);
per-class and per-condition tests are exploratory and uncorrected for multiple comparisons
(the person/car result is the most believable of them, since it appears on both benchmarks); the
mixed run also takes twice as many optimizer steps per epoch (460 vs 230 batches) and trains on
twice as many images, so "more data or more compute" is not ruled out. Two useful side
findings: (1) real-trained runs are far more stable than synthetic-only ones (BDD100K sd 0.11-0.28
vs a 0.6 AP swing between two identical synthetic-only runs), so a gain this size is
detectable; (2) the earlier single local mixed run (+1.2 AP) was optimistic -- the repeated
estimate is about half of it, and the cluster real-only runs (28.15-28.35) reproduce the local
real-only 28.09 closely, supporting that cluster and local runs behave alike.

**Next:** (1) a real-only run on 3,676 real images, to compare synthetic against real image for
image and separate "more data" from "synthetic data"; (2) a compute-matched real-only control;
(3) a data-efficiency sweep (25% / 50% real + synthetic); (4) synthetic data aimed at the weak
spots this identified -- more person and car variety, and night -- since bus/truck/night showed
nothing.

