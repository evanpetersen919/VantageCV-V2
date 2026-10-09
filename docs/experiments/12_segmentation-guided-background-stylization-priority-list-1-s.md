## Segmentation-guided background stylization (priority-list #1, Step 1) — negative result, real diagnosis

**Change:** `bin/stylize_backgrounds.py` (Tobin et al. 2017's domain-randomization technique:
replace the background with a random solid color, gradient, or checker pattern, using this
project's own per-instance segmentation masks to leave every labeled object's pixels exactly
untouched). Applied to all 2,037 v5 images (no re-render), trained one new scratch arm
(`synth_scratch_v5_stylized`, 200 epochs, mosaic=0, identical hyperparameters to v5) on the
result, then Grad-CAM'd and evaluated it exactly like every other arm.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v5 → v5-stylized | 4.0 / 8.7 → **0.2 / 0.4** | 7.8 / 15.4 → **0.4 / 0.7** |

**Verdict: this made things dramatically worse, not better, on both AP and Grad-CAM.** The
new checkpoint's Grad-CAM overlay shows attention *still* dominated by foliage (if anything
more diffusely spread than v3's), plus new hot spots on the road/curb surface, with almost no
distinguishing signal on the actual vehicle in frame. **Root cause, confirmed by direct
measurement, not guessed:** labeled objects cover only ~6% of the average frame's pixels in
this project's wide-street scenes (measured on a real image: 124,075 of 2,073,600 px) — so
this transform replaced ~94% of every training image with flat, textureless synthetic color.
This is a real, meaningful difference from both papers this technique was drawn from: Tobin et
al. 2017's near-field robot-grasping scenes have the object filling much more of the frame,
and Geirhos et al. 2019's Stylized-ImageNet still has rich painterly *texture* everywhere
(decorrelated from class identity, but never textureless), not flat color voids. Removing
almost all learnable low-level pixel statistics from an already-small (1,838-image),
from-scratch training set is a plausible, well-supported explanation for a collapse this
severe, not a sign the underlying domain-randomization hypothesis (still well-supported by
Geirhos/Tobin/Tremblay) is wrong for this project — the *calibration* of this first attempt
was too extreme for a wide-scene/tiny-object/small-dataset regime, not the mechanism itself.

**Next step, not yet done:** a properly calibrated retry — likely (a) textured random noise
(e.g. Perlin/simplex) instead of flat solid/gradient/checker fills, so the background still
carries the kind of low-level statistics a CNN's early layers need to bootstrap general
features, and/or (b) applying the background swap to only a fraction of training images per
epoch (Tremblay et al. 2018 themselves recommend mixing domain-randomized data with more
realistic renders rather than training on pure DR alone, for exactly this stability reason),
rather than the all-images, fully-flat version tested here. Logged honestly as a negative
result rather than omitted, per this project's own stated diagnostic discipline.

