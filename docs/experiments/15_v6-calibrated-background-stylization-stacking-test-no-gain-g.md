## v6 + calibrated background stylization (stacking test) — no gain, Grad-CAM mixed

**Change:** the calibrated `bin/stylize_backgrounds.py` setting (50% of images, 70% noise
fills) applied to the v6 images (no re-render), then the same scratch recipe (200 epochs,
mosaic=0). Tests whether render-side material jitter (v6) and post-render background
randomization add up. **Run note:** training hung at the start of epoch 191 (the
close-mosaic dataloader rebuild, an intermittent Windows deadlock -- the v5 and v6 runs passed
the same step), idle for ~30 minutes; it was resumed from the epoch-190 checkpoint
(`resume=True`) and completed all 200 epochs, so the final 10 epochs ran in a second process.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v6 → v6-stylized | 4.1 / 8.7 → 4.0 / 8.4 | 6.6 / 13.5 → 6.2 / 12.8 |
| (reference) v5-stylized (calibrated) | 4.2 / 9.2 | 7.0 / 14.5 |

**Verdict: stacking did not help.** AP is flat on BDD100K and slightly lower on Cityscapes
(person AP is the weakest class on both). Grad-CAM is mixed: on the Cityscapes truck image the
truck now glows clearly (an improvement), but the BDD100K two-car image is *more* diffuse than
the earlier calibrated-stylization result, with strong activation across the sky and treetops
at the top of the frame. **The more important finding is about the evidence itself:** every
comparison in this entry and the two before it is a single training run per arm, and the
differences (about 0.1-1 AP, and a Grad-CAM pattern that changes between near-identical
recipes) are the size one would expect from seed-to-seed variance. The earlier "first clear
positive Grad-CAM shift" (v5-stylized) may therefore be partly or wholly noise -- it is no
longer safe to build on it without measuring variance. **Next step:** repeat one scratch arm
(v5-stylized and the v5 baseline) with a different training seed on the same data, which
needs no render, to measure run-to-run variance before spending anything on further
interventions.

