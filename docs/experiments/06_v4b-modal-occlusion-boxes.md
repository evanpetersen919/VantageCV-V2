## v4b — modal occlusion boxes

**Change:** `bin/regenerate_modal_boxes.py` regenerated v3's annotations only (same 2,037
images, no re-render), shrinking occluded-object boxes to their visible region via
`occlusion.py`'s new `visible_region_box` (reuses the same ray-cast hit data
`visible_fraction` already computed, refactored into `_hits_and_visibility` so both share
one hit grid and occluder search) instead of keeping the full un-occluded extent above the
0.5 visibility floor. Confirmed via BDD100K's official annotation instructions (direct
quote) that real ground truth boxes only the visible portion for both truncation and
occlusion — independent of v4a's pixel-realism hypothesis, tested in isolation for the same
reason. Verified the fix actually engages before running at full scale: a 50-scenario sample
showed 561 of 1,404 boxes (40%) shrink meaningfully (median shrink ratio 0.29 among those
affected), not just in theory.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v3 → v4b | 2.7 / 5.7 → **3.6 / 7.5** (person 4.3→5.1, car 5.4→7.1, bus 0.3→0.8, truck 0.7→1.3 — every class up) | 4.3 / 7.2 → 4.3 / 8.1 (flat; car up 7.8→10.4, bus/truck down — tiny ground truth, 98/93 boxes) |
| Fine-tune v3 → v4b | 6.1 / 11.8 → 6.3 / 12.0 (roughly flat) | 12.9 / 21.1 → 12.4 / 20.4 (slight regression) |

**Verdict: a real, modest gain on the scratch arm's BDD100K score (+0.9 AP, ~33%
relative), consistent across all four classes together — a meaningful pattern, not
single-class noise. Fine-tune is roughly flat on both benchmarks, and Cityscapes shows no
clear gain either arm.** Plausible mechanistic reason for the scratch/fine-tune split: a
from-scratch model is more sensitive to exactly what box shape it's taught, while fine-tune
starts from strong COCO priors a label-convention fix moves less. Box-convention correctness
is now confirmed to matter somewhat, but like v4a it isn't the dominant lever either — real
transfer still isn't close to the COCO-pretrained baseline (34.8 AP) or the real-control
arm (28.1 AP).

