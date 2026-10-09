## Grad-CAM v3 — rebuilt tool, first v5 baseline (priority-list #1, Step 0)

**Change:** the Grad-CAM script that produced every prior finding (`runs/gradcam/`,
`runs/gradcam_v2/`) was never committed and no longer exists anywhere in the repo or its git
history -- rebuilt as `bin/gradcam_compare.py`, a real, tracked tool, using
`pytorch_grad_cam` (already installed in `.venv-train`) for the CAM math rather than
reimplementing it by hand. Hooks the same three detection-scale feature maps as before,
confirmed against the actual model graph this time (`model.model.model[16]`/`[19]`/`[22]` --
the P3/P4/P5 inputs to YOLOv10's detect head), targeting the model's own single highest
class-confidence cell (any class, any anchor). Reuses the exact same 11-image real panel (5
BDD100K day, 3 BDD100K night, 3 Cityscapes) so overlays are directly comparable to the
surviving `runs/gradcam_v2/` PNGs. Ran against all 8 available checkpoints (v3/v4a/v4b/v5,
scratch + fine-tune each) for a complete, consistent, single-methodology comparison --
including v5, for which no Grad-CAM evidence existed before now.

**Verdict (scratch arm, the more diagnostic one since fine-tune inherits COCO's own shape
priors and shows much cooler, already object-concentrated activation regardless of arm):
real but partial, condition-dependent improvement, not a fix.** On multiple daytime images
(BDD100K and Cityscapes), v5's hottest activation band visibly shifted from being entirely
off-object in v3 -- concentrated in tree canopy, signage and sky, nowhere near either vehicle
in frame -- to running along the actual vehicle body/curb line in v5, with foliage still warm
but no longer the single hottest region. At night, neither version attends to real objects:
v3's heat sits in a flat, uniform top-of-frame border band (a pure image-position artifact),
while v5 replaces that with diffuse, scattered noise across the whole frame -- different
failure mode, not a fix, and consistent with night's persistently lowest AP across every arm
in this entire log. Net: v5's camera/material/tree-species batch measurably reduced (not
eliminated) spurious-texture dominance in daytime conditions, while night remains
untouched -- confirms priority-list #1 is still open, but for a more specific reason than
before: **trees/foliage have no appearance-override mechanism in this pipeline at all** (a
real capability gap traced this session, see the priority-list update below), so no fix
shipped so far could have touched that specific cue directly. Full 88-overlay panel (8
checkpoints x 11 images) at `runs/gradcam_v3/` (untracked, same convention as `gradcam_v2/`).

