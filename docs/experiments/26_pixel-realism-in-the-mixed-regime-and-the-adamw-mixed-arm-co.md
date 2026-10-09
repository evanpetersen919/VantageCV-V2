## Pixel realism in the mixed regime, and the AdamW mixed arm completed (cluster, 3 seeds)

**Realism post-process, 25% real.** The v4a processing (Gaussian blur sigma 0.4, saturation x 0.75,
JPEG quality 75, calibrated earlier against BDD100K's sharpness, saturation and compression) was
applied to the v5 synthetic images (labels unchanged, `train2000_v5_realism`) and mixed with 460
real images, AdamW, 3 seeds (`hpc_realism25`), against the same images unprocessed (`hpc_mixed25`):

| BDD100K | mixed25 | realism25 | difference |
|---|---|---|---|
| AP | 22.93 ± 0.35 | 22.66 ± 0.48 | **-0.27 (p = 0.49)** |
| person / car / bus / truck | 18.05 / 39.51 / 15.72 / 18.43 | 18.18 / 39.54 / 14.97 / 17.97 | +0.13 / +0.03 / -0.76 / -0.47 (all n.s.) |
| night AP | 18.40 | 18.50 | +0.10 (p = 0.71) |

Cityscapes AP 23.17 → 22.89 (-0.28, p = 0.46). Per-seed BDD100K AP: mixed25 23.00 / 23.24 / 22.55,
realism25 22.74 / 23.10 / 22.15. **No effect, on either benchmark, in any class or at night.** The
processing closes the measured pixel gaps (that is what it was calibrated for), so low-level
sharpness, saturation and JPEG statistics are not what separates this generator's images from real
ones as far as detection training is concerned, at least for this simple processing and regime.
Consequences: image-level appearance work (photorealism enhancement, camera/ISP simulation,
diffusion translation) is deprioritised and the effort stays on content, layout and labels; this
entry also settles that v4a's earlier synthetic-only result was not hiding a mixed-regime gain.
Caveats: one processing recipe at one regime (25% real, v5 images); a learned enhancement could
change more than blur and colour; three seeds.

**AdamW mixed arm, all three seeds.** The seed-1 re-run (`hpc_adamw_mixed_s1`) scores 30.03 BDD100K
AP against 30.05 and 29.89 for seeds 0 and 2 (the invalid run read 25.63), so the arm is
**29.99 ± 0.09** with n = 3. Results that were provisional with two seeds, now confirmed:

| Comparison (AdamW, 3 seeds each) | BDD100K AP | Cityscapes AP |
|---|---|---|
| 1,838 real + 1,838 synthetic vs 1,838 real, step-matched (400 epochs) | **+2.02 (p = 0.006)** | **+3.20 (p = 0.017)** |
| same vs the 200-epoch real-only run | +1.71 (p < 0.001) | +2.71 (p = 0.020) |
| + 3,691 synthetic vs + 1,838 synthetic | +0.95 (p = 0.015) | +0.07 (p = 0.85) |
| 1,838 real + 1,838 synthetic vs 3,676 real | -2.80 (p = 0.006) | -2.60 (p = 0.005) |
| 1,838 real + 3,691 synthetic vs 3,676 real | -1.85 (p = 0.005) | -2.53 (p = 0.004) |

The per-class pattern is as before: person +2.2 and car +1.1 over the step-matched baseline (p ≤ 0.001),
truck +2.0 (p = 0.007), bus +2.7 (p = 0.07); versus equal-count real data the gap is largest for truck
(-4.3, -3.0 with the second batch) and bus. Headline, now with every number at n = 3: synthetic
images from this generator improve a detector at every real-data size tested (+4.7, +3.3, +2.0
AP at 460, 919 and 1,838 real images), about 3-7 synthetic images per real one, and lose to the
same number of real images by 2-3 AP.

