## Scanned, photographic street trees (2026-10-10)

The generated card trees of entries 32 and 33 were judged "super fake" by the owner, who asked for high-polygon trees and,
if they were too heavy, fewer of them. This entry replaces them with a photogrammetry scan. It is the template
`configs/scenario_templates/urban_dense_v17.yaml` (v16 with `road_network.photoreal_trees: true` and 13 m tree
spacing); v16 and earlier are unchanged.

![Four frames with scanned street trees: three by day, one at night](../images/foliage_check.jpg)

**What was used.** Poly Haven `jacaranda_tree` (Rob Tuytel and Rico Cilliers, CC0): 3.6 million vertices, 19.5 m tall, 2K
textures for trunk, branches and leaves. Chosen from the site's tree list by looking at every candidate: the others are
tropical island trees (1.7 to 4.7 million triangles), conifers (up to 17 million) or desert quiver trees; this is the only
broadleaf with a street-tree crown. It is imported as a Nanite mesh (`unreal_plugin/tools/prepare_photoreal_trees.py`,
`setup_photoreal_trees.py`), with project-owned materials: opaque for trunk and branches, masked two-sided foliage for the
leaves. Each tree is scaled to 9 to 12.5 m and turned at random; the leaf material is swapped per season through
`material_replacements` (spring, summer, fall; fall uses a hue-shifted copy of the leaf texture; winter keeps Epic's bare
trees). Class: `vegetation` by asset path.

**Result** (16 frames of 8 scenes, forced summer, v17, class maps; the same seeds as entries 32 and 33):

| | Cityscapes val | Cards, entry 33 | Scanned (13 m spacing) |
|---|---|---|---|
| vegetation, all frames | 17.1% | 16.0% | **16.8%** |
| vegetation per frame, median | 16.2% | 16.0% | **16.9%** |
| vegetation per frame, min / max | quartiles 8.0 / 25.0 | 7.4 / 21.4 | **6.6 / 27.2** |
| terrain | 0.6% | 0.5% | 0.5% |
| building | 20.9% | 28.8% | 27.8% |
| sky | 3.3% | 7.2% | 7.4% |
| mean vegetation colour (sRGB) | (51, 62, 49) | (62, 67, 46) | (57, 54, 33) |

The per-frame spread now covers the real quartiles (the cards never reached the upper one). The mean colour is **worse on
blue and green**: the scanned leaves are light, warm and sparse, and trunk and branches are in the vegetation mean; the tint
(`LEAF_TINTS`) was raised in blue once and not tuned further.

**Density and cost.** With the 20.21 m spacing of Epic's placements the share was 11.3% (median 9.0%); 13 m reaches the real
share. The scenes are cheaper than the card trees: 346 s for 8 scenarios (16 frames) against 1,080 s for the card version,
because a tree is an asset path and a transform, not 50 MB of mesh JSON. Nanite carries the triangle count.

**Machine note.** One crash came from the host, not the project: a dozen `SteelSeriesCaptureSvc` processes held over 100 GB of
commit charge (118 of 128 GB), so shader compilation of the new material ran out of memory ("paging file too small"). Ending
those processes freed it (committed memory fell to 25 GB).

**Licence.** Poly Haven and ambientCG are CC0; the sources are recorded in `LICENSING.md` (section "Vegetation textures and
models").

**Checks run:** 8 unit tests (`tests/unit/test_photoreal_trees.py`): no trees in winter or without spots, the right leaf
material per season, tree on its spot at a street-tree height, determinism, v17 putting scanned trees where v16 puts card
meshes and removing Epic's, winter keeping the bare trees, and the payload carrying the leaf swap.

**Not done, and open**
- One tree model only, so every street shows one species with different sizes and turns; more scans would help (Poly Haven
  has few broadleaf street trees; the Fab/Megascans ones are not CC0).
- Shrubs and hedges are still the card meshes of entry 33, and look it next to the scanned trees. Poly Haven has scanned
  shrubs (`shrub_01` to `shrub_04`, 17k to 282k triangles); the lawn is a photographic tile but flat.
- Colour: blue and green still low; night trees are dark.
- No detection result yet shows whether any of this helps a trained detector.
