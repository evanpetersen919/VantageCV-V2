## Tree quality and curb planting: grass, shrubs, hedges (2026-10-09)

Entry 32 added generated leafy trees and brought vegetation to 14.8% of pixels, but the owner's review of the frames was
that the trees "look super fake". The causes were visible: each leaf card was lit as a flat quad (the engine computes
normals per card), every card had the same brightness and colour, the leaf texture repeated identically, crowns were
plain balls, and trunks were straight bare tubes. This entry fixes those and adds street-level vegetation (the owner
asked for more). Both are in `configs/scenario_templates/urban_dense_v16.yaml`; older templates are unchanged.

![Four frames with the improved trees, grass strips, shrubs and hedges: three by day, one at night](../images/foliage_check.jpg)

**Tree quality** (`src/procedural/foliage.py`)
- **Smooth shading.** Meshes can now carry per-vertex normals and vertex colours (new optional `normals` and `colors` in
  the mesh payload, read by `ProceduralScenarioLoader.cpp` and `ScenarioMeshBuilder.cpp`; meshes without them are sent
  and built exactly as before). Each card vertex gets its lump's outward normal (80%) mixed with the card's own, so light
  falls off across the crown instead of card by card.
- **Depth and variation.** Each card's vertex colour darkens cards deep inside a lump and underneath it and jitters
  brightness (12%) and hue (8%); the brightest are capped at 0.88 so sunlit leaves do not blow out to white. The card
  texture is turned by a random quarter turn and mirrored per card. The leaf texture now varies in hue per leaf.
- **Shape.** Crowns are 3 to 5 overlapping lumps, each tree's crown width varies 0.75 to 1.3 times, the crown leans up to
  0.6 m off the trunk's foot, trunks flare at the base and fork into two branches per lump, and trunk and branches carry a
  generated furrowed-bark texture (`T_Bark.png`, tileable, made with FFT-filtered noise).
- **Material.** `M_Foliage` uses Unreal's two-sided-foliage shading model, the subsurface colour equal to the base colour
  (light shows through leaves), low specular, and the vertex colour in the base colour.

**Planting** (`src/procedural/planting.py`; layout and mix are design choices, not measurements)
- Intermittent grass patches beside the curb on the sidewalk, 1.0 m wide and 8 to 18 m long with 3 to 8 m gaps, a
  centimetre above the sidewalk slab, away from run ends and driveway keep-out rectangles (a keep-out only removes
  patches; the layout of the others does not change). Material `grass` (generated tileable texture, `M_Grass`), class
  `terrain`.
- Each patch is plain lawn (35%), spaced shrubs (40%, 1.6 to 2.6 m apart, 65% filled) or a dense hedge (25%, lumps every
  0.7 m, 0.9 to 1.2 m high). Shrubs are the tree generator's leaf-card lumps at 0.5 to 0.8 m radius with the season's
  foliage material, none in winter.

**Tints from data.** Real vegetation in 167 Cityscapes validation images: mean sRGB (51, 62, 49); terrain (56, 67, 51).
Tints were scaled against our own rendered vegetation pixels over three runs (mean (57,64,38), then (79,83,57) after the
shading change, then (68,73,51), now (62,67,46)).

**Result** (16 frames of 8 scenes, forced summer, v16, class maps):

| Class | Cityscapes val | Ours, entry 32 | Ours now |
|---|---|---|---|
| vegetation | 17.1% | 14.8% | **16.0%** |
| terrain | 0.6% | 0.0% | **0.5%** |
| building | 20.9% | 28.6% | 28.8% |
| sky | 3.3% | 7.6% | 7.2% |

Per frame, vegetation has median **16.0%** (min 7.4, max 21.4) against Cityscapes' median 16.2% (quartiles 8.0 and
25.0). Mean vegetation colour **(62, 67, 46)** against the real (51, 62, 49): closer than before: red 21% and green 8% above
the real mean, blue 6% below. The sunlit lawn strips still look brighter and more saturated than real grass in some
frames.

**Cost, honestly.** Trees and shrubs are large meshes: about 520,000 vertices in a typical scene, 51 MB of JSON after
rounding vertices and normals to a millimetre (without it, 120 MB, which hung the game on load once). Scenario rendering
went from about 40 to 90 s to **about 110 to 200 s per scenario** (two frames each) in this configuration, which
matters for any batch. Instancing the trees (one mesh, many transforms) would remove most of it; not done.

**Checks run:** 14 unit tests in `tests/unit/test_foliage.py` (including the payload carrying rounded normals and colours
and plain meshes staying byte-identical in shape) and 6 in `tests/unit/test_planting.py` (determinism, keep-outs only
removing patches, patch width and length, upward grass quads at the right height, shrubs only in leafy seasons and only
on planted patches, off by default). Full suite, lint 10/10 and mypy strict clean.

**Not done, and open**
- Still a stylised look up close: flat-coloured leaves of one shape, no individual branch structure, one species
  silhouette family; judged only by eye. The comparison with real photos is class share and colour, not a perceptual
  test.
- Building share (28.8% vs 20.9%) and sky share (7.2% vs 3.3%) remain high; poles (0.0% vs 1.8%) and traffic signs (0.0%
  vs 0.7%) are not labelled in these class maps' comparison classes.
- No detection result yet shows whether any of this vegetation helps a trained detector.
- Night trees are dark but plausible; not calibrated.
