## Synthetic pre-training then real fine-tuning, vs mixed training (cluster, 3 seeds each)

Question: is learning from the synthetic images first and then fine-tuning on real ones a better
use of them than mixing both in one run? Three synthetic-only pre-training runs (`hpc_pretrain_s0-2`:
v5 images, scratch, 200 epochs, mosaic off), then for each seed three fine-tunes from that seed's
`best.pt` on 25% / 50% / 100% of the control's real images (50 epochs, mosaic on, close-mosaic 10;
fine-tune seed k starts from pre-train seed k). Same cluster, validation set and scoring as the
earlier cluster entries. All 66 result files in `results/hpc_*` were checked for image counts and
that each points at its own weights.

Synthetic-only pre-train (the starting point): BDD100K AP **3.75 ± 0.13** (3.60 / 3.80 / 3.84),
Cityscapes 6.20 ± 0.37 -- consistent with the local v5 scratch numbers, and much tighter across
seeds than the 0.6-2.5 AP swings seen locally.

BDD100K AP, mean ± sd over 3 seeds (Cityscapes in brackets):

| Real images | Real only (200 ep) | Pre-train → fine-tune (50 ep) | Mixed (200 ep) | Fine-tune minus mixed |
|---|---|---|---|---|
| 460 (25%) | 18.23 (18.67) | 22.08 ± 0.42 (21.75) | 22.93 (23.17) | **-0.85** (p = 0.057); Cityscapes -1.42 |
| 919 (50%) | 23.02 (22.05) | 25.09 ± 0.21 (24.20) | 26.28 (25.44) | **-1.19** (p = 0.003); Cityscapes -1.24 |
| 1,838 (100%) | 28.28 (26.35) | 28.31 ± 0.36 (26.15) | 28.94 (27.52) | **-0.63** (p = 0.077); Cityscapes -1.37 |

Fine-tuning beats real-only at 25% and 50% (+3.85 p = 0.002, +2.07 p = 0.002; Cityscapes +3.08,
+2.16) and ties it at 100% (+0.03, p = 0.91), the same shape as mixed training but smaller. **Mixed
training was ahead of fine-tuning in all six fraction x benchmark comparisons** (BDD100K p = 0.057,
0.003, 0.077; Cityscapes p = 0.08, 0.07, 0.22 -- individually borderline, jointly consistent). The
deficit sits mostly in bus (-2.3, -3.6, -1.4 AP on BDD100K) and truck (-0.8, -0.6, -0.1); person and
car are within about 0.6 AP of mixed at every fraction. Person is the one class that gains over
real-only under both methods even at 100% real data (mixed +1.9, fine-tune +1.3 BDD100K, p = 0.003;
Cityscapes +2.1 and +1.5), and the only gain that survives to the largest real set.

**Verdict:** pre-training then fine-tuning is not better than mixed training -- it is about 0.6-1.2
AP behind on BDD100K -- but it recovers most of the benefit (+3.9 of mixed's +4.7 at 25% real) with
a quarter of the real-data training epochs. **Mixed training stays the default recipe.**
Caveats, stated plainly: the two recipes are not compute-matched (fine-tune runs 50 epochs on the
real images, mixed 200); only one fine-tune length and the default learning rate were tried, so a
longer or lower-rate fine-tune might close the gap; pre-train weights were chosen on a synthetic
validation split; three seeds per arm and borderline p-values; bus/truck have few ground-truth
boxes on Cityscapes (98 and 93; BDD100K has 1,597 and 4,231, but only 302 and 746 at night), so
those differences are noisy.

**Next:** the second-batch volume test is running (real + 3,691 synthetic at 25% and 100% real).

