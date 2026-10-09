## v2 — occlusion label fix only

**Change:** re-exported v1's existing images with a stricter kept-visibility floor
(`visibility_fraction >= 0.5` instead of `>= 0.1`), dropping annotations for majority-hidden
objects that were still being boxed at full un-occluded extent (44% of v1's boxes had
visibility_fraction < 0.5). No new images rendered; no other change.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch | 3.0 / 6.4 | 2.7 / 5.7 |
| Fine-tune | 6.2 / 12.4 (car AP 10.6→13.5) | 11.0 / 20.5 |

**Verdict:** small, real gain on fine-tune; scratch unchanged. Confirmed the occlusion-box
issue was real but not the dominant gap.

