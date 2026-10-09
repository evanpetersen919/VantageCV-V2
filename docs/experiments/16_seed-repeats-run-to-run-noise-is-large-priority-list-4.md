## Seed repeats — run-to-run noise is large (priority-list #4)

**Change:** none to the data or recipe; the training seed only (`--seed 1`) for the v5 baseline
and for the calibrated-stylization arm (v5 images with backgrounds randomized, 50% of images /
70% noise fills), scratch, 200 epochs, `--close-mosaic 0` (identical augmentation, since mosaic
is already off, but it skips the end-of-run dataloader rebuild that deadlocked once -- see the
v6 + stylization entry).

| Arm | BDD100K AP / AP50, seed 0 → seed 1 | Cityscapes AP / AP50, seed 0 → seed 1 |
|---|---|---|
| v5 baseline | 4.0 / 8.7 → 3.4 / 7.5 | 7.8 / 15.4 → 5.3 / 11.4 |
| v5 + calibrated stylization | 4.2 / 9.2 → 4.3 / 9.1 | 7.0 / 14.5 → 6.9 / 14.0 |

**Verdict: two runs of the identical recipe differ by 0.6 AP on BDD100K and 2.5 AP on
Cityscapes (the v5 baseline), so single-run differences below roughly that size cannot be told
apart from noise -- this covers v4b, v6, and both stylization tests as originally read.** It
also weakens the v3 → v5 gain: v3's Cityscapes AP was 4.3 (one run), against v5 runs of 7.8
and 5.3, so the gain is anywhere from about +22% to +80% depending on the seed (BDD100K about
+27% to +49%); the direction is probably real, the size is not. v3 itself is one run and was
trained with mosaic on (v5 off), so the v3 → v5 comparison also mixes the render fixes with
the augmentation change. The stylized arm was consistent across both seeds (BDD100K 4.2 and
4.3, above the baseline's 4.0 and 3.4; Cityscapes 7.0 and 6.9, overlapping the baseline's
range) -- suggestive that background randomization stabilizes training, not proven with two
seeds per arm. The seed-1 Grad-CAM panels have not been reviewed yet.

