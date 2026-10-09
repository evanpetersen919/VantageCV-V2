## v6 — always-on material appearance jitter (priority-list #1, Step 2) — no measurable gain

**Change:** `src/procedural/environment.py` now applies a per-scenario random tint /
roughness / specular jitter to building and asphalt/pavement/ground surfaces on *every*
scenario (day, night, any weather); before this, those parameters only varied when it was
raining. It reuses the exact override parameters the rain preset already proved reach the live
materials, with wide, deliberately non-realistic ranges (Tobin et al. 2017 / Tremblay et al.
2018), and leaves rain's own wetness values untouched. Pure Python, no plugin rebuild. A full
re-render (same 800 seeds and bounds as v3/v5, 2,037 images, calibration 0.53 px), then the
same scratch (200 epochs) and fine-tune (50 epochs) recipe, mosaic=0, as v5.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v5 → v6 | 4.0 / 8.7 → 4.1 / 8.7 (flat) | 7.8 / 15.4 → 6.6 / 13.5 (down) |
| Fine-tune v5 → v6 | 6.4 / 12.8 → 6.4 / 12.1 (flat) | 12.0 / 22.4 → 12.1 / 21.8 (flat) |

**Verdict: no measurable benefit.** BDD100K is flat on both arms, fine-tune Cityscapes is
flat, and scratch Cityscapes dropped 1.2 AP -- one run, on a 500-image benchmark whose bus/truck
classes have under 100 boxes each, so this is within the range the earlier statistical-rigor
review flagged as possible run-to-run noise, not evidence of harm. Grad-CAM (same panel) looks
like the v5 baseline: diffuse, with the hottest spots on the dashboard/hood and the curb line,
and clearly less vehicle-focused than the calibrated background-stylization retry above.
**Interpretation:** mild per-surface tint/roughness jitter keeps every texture's *identity*
(foliage still looks like foliage, curbs like curbs) and its structure, so the network can
still key on them; the post-render background randomization worked (qualitatively) because it
removed that structure entirely. Foliage also remains untouched by this change -- trees still
have no appearance-override mechanism (the Step 3 gap). Not yet tested: whether the two effects
stack (stylization applied to v6 images), or a repeat seed to measure the variance.

