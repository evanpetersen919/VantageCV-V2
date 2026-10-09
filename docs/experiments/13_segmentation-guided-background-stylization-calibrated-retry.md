## Segmentation-guided background stylization, calibrated retry — real, positive Grad-CAM shift, AP roughly flat

**Change:** `bin/stylize_backgrounds.py` updated per the negative result above: 70% of
stylized backgrounds now use multi-octave value noise (colorized between two random colors,
a cheap dependency-free Perlin-noise approximation) instead of a flat solid/gradient/checker
fill, so the background keeps real per-pixel edge/gradient/contrast statistics everywhere in
the frame; and only 50% of images get any background swap at all, so half of every training
batch still has a real, unmodified background (Tremblay et al. 2018's own recommendation).
Same training config as every other arm (200 epochs scratch, mosaic=0), same Grad-CAM panel.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Scratch v5 → v5-stylized (flat, 100%) | 4.0 / 8.7 → 0.2 / 0.4 (collapsed) | 7.8 / 15.4 → 0.4 / 0.7 (collapsed) |
| Scratch v5 → v5-stylized2 (noise, 50%) | 4.0 / 8.7 → **4.2 / 9.2** (car 19.9→23.2, truck 1.7→3.0 up; person 11.2→8.2 down) | 7.8 / 15.4 → 7.0 / 14.5 (car 32.5→35.1 up; person/bus down slightly) |

**Verdict: the collapse is fully fixed (confirms the earlier diagnosis was correct), and
Grad-CAM shows a real, visible, positive shift -- but AP stayed roughly flat, not better.**
On the same 3 images inspected for every prior arm: the BDD100K car image's hottest
activations now sit directly on both vehicles' taillights (a real, legitimate object cue) with
foliage/signage now clearly cooler than in v3's version of the same image. The Cityscapes
truck image shows a similar shift -- foliage cooled, a real warm patch appears on the truck
itself, hottest activation moved to the curb line rather than the tree canopy. Even the
persistently-weak night image shows heat concentrating around the actual visible vehicle
cluster in the middle distance (plus a lane-line diagonal -- road structure, still not the
vehicle itself, but geometrically meaningful rather than pure scattered noise), a step up from
both v3's frame-border artifact and the first stylized attempt's undirected noise. **This is
the first change in this entire log where Grad-CAM moved clearly and positively on a majority
of inspected images** -- every other arm (v4a, v4b, v5, the failed first stylization attempt)
either left attention unchanged or made it worse. That AP didn't rise to match is itself an
informative, honest result: a real reduction in spurious-texture reliance doesn't
automatically show up as an AP gain at this dataset scale (1,838 training images) -- consistent
with priority-list item #3 (dataset scale) potentially gating how much benefit a shape-bias
fix alone can produce. Full overlay comparison at `runs/gradcam_v3/` (files suffixed
`_v5_stylized2_scratch`).

**Recommended next step:** this result justifies moving to the plan's Step 2 (push the
existing renderer-side material/tint randomization harder, always-on rather than rain-gated)
on a real re-render, now that the Grad-CAM-positive mechanism is confirmed cheaply in Python
first -- exactly the staged, cost-ordered approach the plan called for. Done: see the v6
entry below.

