# Configs

| Path | What it is |
|---|---|
| `scenario_templates/urban_dense.yaml`, `urban_sparse.yaml` | The two scenario types the generator builds today (v6 traffic mix). |
| `scenario_templates/highway.yaml`, `parking_lot.yaml`, `roundabout.yaml` | Reference only: `load_scenario_config` raises `NotImplementedError` for them (see `src/procedural/config_loader.py`). |
| `scenario_templates/urban_dense_v7.yaml` | Current default: traffic mix matched to measured BDD100K class shares (`--profile v7`). |
| `scenario_templates/urban_dense_v7_peds.yaml` | v7 with the v6 pedestrian density (batch `train_v7p`). |
| `scenario_templates/urban_dense_v7_nopeds.yaml` | v7_peds with no pedestrians (batch `train_v10n`). |
| `scenario_templates/urban_dense_v8a.yaml`, `urban_dense_v8b.yaml` | Truck/bus mix experiments on the v7 profile (batches `train_v8a`, `train_v8b`). |
| `scenario_templates/urban_dense_v11.yaml` | v8a plus the box-truck fleet pilot (batch `train_v11`). |
| `scenario_templates/urban_dense_v14.yaml` | v13r plus painted lane markings (`road_network.lane_markings: true`): double yellow centre lines, white lane lines, stop lines. |
| `scenario_templates/urban_dense_v15.yaml` | v14 plus signal states (`road_network.signal_states: true`): each signal pole shows its intersection's phase, poles only at signalized intersections. |
| `scenario_templates/urban_dense_v16.yaml` | v15 plus greenery: leafy street trees (`road_network.foliage: true`, `street_tree_spacing_m: 12.0`) and curb grass, shrubs and hedges (`road_network.planting: true`). |
| `scenario_templates/urban_dense_v17.yaml` | v16 with scanned photographic street trees (`road_network.photoreal_trees: true`, Poly Haven CC0, Nanite) at 13 m spacing. |
| `scenario_templates/urban_dense_v13r.yaml` | v7_peds with Rocketbox pedestrians (batch `train_v13r`, the Kaggle release config). |
| `generation_config.yaml` | Dataset-level defaults; the scenario-type weights in it are not read by any code yet. |
| `sensor_profiles/` | Camera profiles. |
| `material_tags.json`, `rocketbox_catalog.json` | Asset tagging and the 38-avatar Rocketbox catalogue. |

The `_vN` files are frozen snapshots of what produced a logged batch (`EXPERIMENT_LOG.md`, `manifest.json`
of each batch). They are not renamed, so the logged commands still reproduce. For a new study copy the
closest file and name it for what it changes.
