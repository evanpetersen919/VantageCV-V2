## Synthetic volume test: a second batch, 3,691 synthetic images (cluster, 3 seeds each)

Question: does more synthetic data help? A second batch (`train2000_v5b`: same generator as v5,
the pre-jitter commit, seeds 20000-20799 so no scene overlaps v5; 2,051 frames, 0 rejected,
calibration 0.53 px; split by scenario like v5 into 1,853 train / 198 val) was added to the first
(1,838), giving 3,691 synthetic training images. Runs: real + both batches at 25% real (460) and at
100% real (1,838), seeds 0/1/2, same recipe and cluster as every other cluster arm. Compared with
the same real data + the first batch only. All 78 `hpc_*` result files re-verified.

BDD100K AP, mean ± sd over 3 seeds (Cityscapes in brackets):

| Real images | Real only | + 1,838 synthetic | + 3,691 synthetic | Doubling synthetic |
|---|---|---|---|---|
| 460 (25%) | 18.23 (18.67) | 22.93 (23.17) | 22.66 ± 0.28 (23.34) | **-0.27**, p = 0.37 (Cityscapes +0.17, p = 0.82) |
| 1,838 (100%) | 28.28 (26.35) | 28.94 (27.52) | 29.87 ± 0.48 (29.21) | **+0.93**, p = 0.058 (Cityscapes +1.69, p = 0.16) |

Against real-only the larger synthetic set gives +4.44 AP at 25% (p < 0.001) and **+1.59 AP at
100% (p = 0.024; Cityscapes +2.86, p = 0.014)** -- the first time the 100%-real gain is significant
on both benchmarks. Still short of equal-count real data: 1,838 real + 3,691 synthetic (29.87) is
2.11 AP below 3,676 real images (31.98, p = 0.014; night -2.95, truck -3.41, bus -2.57, car -1.36,
person -1.11). On Cityscapes it ties 3,676 real images (29.21 vs 29.20, bus +2.7, truck -2.2).

**Per class, the benefit of more synthetic data is consistent for person and car and absent for
bus/truck.** Doubling synthetic: BDD100K at 100% real person +1.05 (p = 0.045) and car +0.55
(p = 0.048); Cityscapes person +1.53 / +1.60 and car +0.52 / +1.15 at 100% / 25% real (all
p < 0.03); at 25% real on BDD100K person +0.58, car +0.56 (p = 0.034). Bus and truck move
inconsistently (BDD100K 25%: bus -1.19, truck -1.01, both n.s.; 100%: +1.33, +0.79).

Reading the real-only curve as a ruler (linear interpolation, approximate): 3,691 synthetic images
are worth roughly +425 real images at 25% real (vs +450 for 1,838) and roughly +790 at 100% real (vs
+330 for 1,838) -- no consistent saturation or acceleration across the two regimes.

**Verdict:** more of this generator's synthetic data is not a strong lever. At low real counts it
adds nothing (-0.27 AP); at 100% real it adds about +0.9 AP (p = 0.058, not clearly significant),
mostly person and car. The earlier headline stands (synthetic data helps when real data is
scarce, roughly 4-5 synthetic images per real one) and doubling the volume does not change it much.
The remaining distance to real data is concentrated in truck, bus and night (-3.4, -2.6, -3.0 AP vs
equal-count real), which points at image content for those cases, not at volume.
Caveats, stated plainly: three seeds per arm and borderline p-values; the larger runs also take more
optimizer steps per epoch (5,529 vs 3,676 images), so extra compute is not separated from extra
data; bus/truck have few ground-truth boxes on Cityscapes (98 and 93) and at night on BDD100K (302
and 746), so their differences there are noisy; both batches come from one generator, so a second batch adds scene variety only to the
extent the seeds do.

**Next:** do not spend effort on faster or larger rendering yet. Look at where the generator is
weakest for truck, bus and night -- instance counts, sizes and models of those classes in the
synthetic set vs BDD100K, and how night frames differ -- and target them.

