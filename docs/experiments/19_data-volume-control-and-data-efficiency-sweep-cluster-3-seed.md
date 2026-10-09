## Data-volume control and data-efficiency sweep (cluster, 3 seeds each)

Question left open by the previous entry: is the +0.66 AP from synthetic images, or just from
having twice as many images? Fifteen further cluster jobs, same recipe and hardware (scratch,
200 epochs, imgsz 960, batch 8, mosaic on, close-mosaic 10, seeds 0/1/2), all validated on the
same 199 real images and scored on BDD100K val (10,000) and Cityscapes val (500). New arms: real
only on 3,676 images (the control's 1,838 plus 1,838 further disjoint BDD100K images); and
25% / 50% of the control's real images, alone and with all 1,838 synthetic images. All 42 result
files were checked for image counts (10,000 / 500) and that each points at its own weights.

BDD100K AP (mean ± sd over 3 seeds); Cityscapes in brackets:

| Real images | Real only | Real + 1,838 synthetic | Gain from synthetic |
|---|---|---|---|
| 460 (25%) | 18.23 ± 0.14 (18.67) | 22.93 ± 0.35 (23.17) | **+4.70, p < 0.001** (+4.50) |
| 919 (50%) | 23.02 ± 0.34 (22.05) | 26.28 ± 0.24 (25.44) | **+3.26, p < 0.001** (+3.39) |
| 1,838 (100%) | 28.28 ± 0.11 (26.35) | 28.94 ± 0.28 (27.52) | +0.66, p = 0.042 (+1.17, n.s.) |
| 3,676 (200%) | 31.98 ± 0.10 (29.20) | -- | -- |

**Control result: 3,676 real images score 31.98 vs 28.94 for 1,838 real + 1,838 synthetic --
real is +3.04 AP better (p = 0.001; Cityscapes +1.68, not significant).** At equal image count,
these synthetic images are worth clearly less than real ones. The +0.66 AP reported above is
therefore a smaller effect than simply adding more real data (+3.70 AP for the same extra
1,838 images), and should not be described as evidence that the images match real data.

**What the sweep shows instead:** the gain from synthetic data is large when real data is
scarce and shrinks as real data grows (+4.7 → +3.3 → +0.7 AP on BDD100K; person +5.6 → +4.0 →
+1.9, bus +5.6 → +4.3 → +0.1, truck +4.4 → +2.8 → +0.0). Night improves at 25% and 50% real
(+3.1, +2.6) and not at 100% (+0.2). The same shape holds on Cityscapes (+4.5, +3.4, +1.2).
Every one of the 12 BDD100K mixed runs at 25% and 50% beats the real-only run at the same
fraction. Reading the real-only curve as a ruler (linear interpolation between measured
points, so approximate): the 1,838 synthetic images behave like roughly +450 / +570 / +330
extra real images at 460 / 919 / 1,838 real images on BDD100K (about +700 on Cityscapes at
every level), i.e. about 3-6 synthetic images per real image, with diminishing returns as the
real set grows.

**Verdict:** synthetic data from this generator is a real, statistically supported help in the
low-real-data regime (a quarter to half of 1,838 images) and a marginal one at 1,838; it does
not replace real data, and at equal count it loses to it by about 3 AP. The headline claim is
now "improves a real-data-limited detector, with about 3-6 synthetic images worth one real image",
not "adds a small gain on top of real data". Caveats, stated plainly: three seeds per arm;
per-class/condition tests are exploratory and uncorrected; the real-image equivalents are
interpolated from a four-point curve and are rough; the real-only curve is still rising at 3,676
images (no plateau), so the gap to synthetic at larger real sizes is unmeasured; one synthetic
set (v5, 1,838 images) was used throughout, so whether more synthetic data helps is untested.

**Next:** (1) the scale test already rendering -- a second disjoint 1,800-image batch with the
same generator, giving 3,676 synthetic images, to test whether the synthetic contribution grows
with synthetic volume (the first measurement of the generator's scaling curve); (2) because the
sweep shows the value is largest where real data is scarce, evaluate at 10-25% real and with
synthetic pre-training followed by real fine-tuning; (3) work on the generator's remaining
domain gap, measured against the equal-count real control (-3 AP) rather than against real-only
at the same real count.

