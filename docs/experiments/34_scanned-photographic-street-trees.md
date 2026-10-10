## Scanned, photographic street trees and shrubs (2026-10-10)

The generated card trees of entries 32 and 33 were judged "super fake" by the owner, who asked for high-polygon trees
and, if they were too heavy, fewer of them. This entry replaces them with photogrammetry scans from Poly Haven (CC0) and
swaps the card shrubs for scanned shrubs. It is the template `configs/scenario_templates/urban_dense_v17.yaml` (v16 with
`road_network.photoreal_trees: true` and 15.5 m tree spacing); v16 and earlier are unchanged.

![Four frames with scanned street trees, shrubs and hedges: three by day, one at night](../images/foliage_check.jpg)

**What was used** (all Poly Haven, CC0, 2K textures; `unreal_plugin/tools/prepare_photoreal_trees.py`,
`setup_photoreal_trees.py`)

| Asset | Used as | Source triangles | Placed height |
|---|---|---|---|
| `jacaranda_tree` | street tree (60% of trees) | 3.6 million | 9 to 12.5 m |
| `tree_small_02` | street tree (40%) | 1.8 million | 6.5 to 9 m |
| `searsia_lucida` (variants a to g) | shrub patches | 8 thousand to 136 thousand | 0.7 to 1.3 m |
| `othonna_cerarioides` (variants a to g) | hedge patches, columnar | 7 thousand to 150 thousand | 0.8 to 1.4 m |
| `fern_02` (variants a to d) | an occasional fern on a lawn patch | 0.5 to 1.7 thousand | 0.35 to 0.6 m |

Chosen by looking at every tree and plant in the site's list: the others are tropical, conifers (up to 17 million
triangles) or desert plants. Leaf material is swapped per season through `material_replacements` (spring, summer,
fall with a hue-shifted leaf texture; winter keeps Epic's bare trees; the shrubs are evergreen and keep summer's).

**Three problems on the way, each found by looking at renders**
1. *Nanite does not work in this pipeline.* The game must run on D3D11 (D3D12 crashes in shader compilation) and D3D11
   cannot draw Nanite: the engine fell back to a reduced proxy (3.6 million vertices became 22,000) and the crowns
   thinned to a few leaves. Nanite is off; heavy meshes get classic LODs (40%, 15%, 5%, 1.5% of the triangles at screen
   sizes 1.0, 0.3, 0.15, 0.06; the jacaranda is 1.8 million, 472 thousand, 200 thousand, 59 thousand vertices).
2. *A placeholder texture leaked into the render.* The parent materials fell back to a flat-normal-map placeholder for
   their diffuse parameter and the first instances showed blue; with the right per-role placeholders the real textures
   show. An earlier render that looked fine was in fact wearing the bark texture on the leaves.
3. *The alpha clip thinned the leaflets.* The scans model each leaflet as geometry (1.46 million leaf polygons), so the
   alpha only trims edges; the default clip of 0.33 with mip-averaged alpha removed many at distance. Clip set to 0.08.
   The Blender check that settled the UV orientation: with no flip the leaf faces land on opaque texels 55% of the time
   (29% with a flip).

**Result** (16 frames of 8 scenes, forced summer, v17, class maps; the same seeds as entries 32 and 33)

| | Cityscapes val | Cards, entry 33 | Scanned, 15.5 m |
|---|---|---|---|
| vegetation, all frames | 17.1% | 16.0% | **15.7%** |
| vegetation per frame, median | 16.2% | 16.0% | **15.2%** |
| vegetation per frame, min / max | quartiles 8.0 / 25.0 | 7.4 / 21.4 | **6.1 / 25.1** |
| terrain | 0.6% | 0.5% | 0.7% |
| building | 20.9% | 28.8% | 28.0% |
| sky | 3.3% | 7.2% | 7.2% |
| mean vegetation colour (sRGB) | (51, 62, 49) | (62, 67, 46) | **(54, 60, 41)** |

Tree spacing set the share: 13 m gave 20.7%, 14.5 m 19.7%, 15.5 m 15.7%, 16 m 14.1% (a single set of 8 scenes, so the
steps are noisy); with Epic's 20.21 m the first version had 11.3%. The per-frame spread now covers the real quartiles.
The leaf tint was raised in green and blue over three runs against the real colour.

**Cost.** The scenes are cheaper to render than the card trees (about 245 to 345 s for 8 scenarios against 1,080 s)
because a plant is an asset path and a transform. The editor setup (reducing 3.6 million vertices to four LODs) takes
about ten minutes once.

**Machine note.** One crash came from the host: a dozen `SteelSeriesCaptureSvc` processes held over 100 GB of commit
charge (118 of 128 GB), so shader compilation ran out of memory ("paging file too small"). Ending those processes freed it
(committed memory fell to 25 GB).

**Licence.** Poly Haven and ambientCG are CC0; the sources are recorded in `LICENSING.md` ("Vegetation textures and
models"). The scans' FBX files and textures are downloaded by the script, not committed.

**Checks run:** unit tests in `tests/unit/test_photoreal_trees.py` (trees by season and spot, size ranges per model,
determinism, v17 replacing card trees and Epic trees, winter, the payload carrying the leaf swaps of both tree models) and
in `tests/unit/test_planting.py` including the scanned shrubs by patch style and season.

**Not done, and open**
- Two tree species only, both scanned in a natural setting rather than as a planted street tree; the crowns are wider
  than a pruned city tree.
- The hedge is a row of columnar shrubs and the lawn is a flat photographic tile; sunlit grass is brighter than real.
- Colour: blue (41 vs 49) and green are still a little low; night trees are dark.
- Building share (28.0% vs 20.9%) and sky (7.2% vs 3.3%) remain high; poles and signs are not in these comparisons.
- No detection result yet shows whether any of this helps a trained detector.
