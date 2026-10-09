# results/

Result files from the evaluations, one JSON per run and benchmark. Nothing here is edited by hand.

## Naming

- `hpc_<arm>_s<seed>_<benchmark>.json`: one trained arm, one seed, scored on `bdd100k` or `cityscapes`. Extra suffixes mark other evaluations of the same run (`_scene`, `_box_outcomes`, `_imgsz...`).
- `baseline_*`, `real_control_*`, `synth_*`, `real_plus_synth_*`, `mosaic_*`, `smoke_*`, `label_audit_*`: the earlier, single-machine runs, before the cluster.
- `carla/`: the CARLA driving comparison.

The Entries column lists the experiment entries (their numbers in [`EXPERIMENT_LOG.md`](../EXPERIMENT_LOG.md)) whose text names the arm, with or without the `hpc_` prefix; an empty cell means no entry names it that way.

## Cluster arms

| Arm | Seeds | Entries |
|---|---|---|
| `hpc_adamw_mixed25big` | 0,1,2 |  |
| `hpc_adamw_mixed` | 0,1,2 | 23, 25, 26 |
| `hpc_adamw_mixedbig` | 0,1,2 |  |
| `hpc_adamw_modal` | 0,1,2 | 25 |
| `hpc_adamw_real3676` | 0,1,2 |  |
| `hpc_adamw_real400` | 0,1,2 |  |
| `hpc_ft100` | 0,1,2 |  |
| `hpc_ft25` | 0,1,2 |  |
| `hpc_ft50` | 0,1,2 |  |
| `hpc_mixed25` | 0,1,2 | 22, 23, 25, 26 |
| `hpc_mixed25big` | 0,1,2 | 22 |
| `hpc_mixed50` | 0,1,2 | 22 |
| `hpc_mixed` | 0,1,2 | 5, 7, 15, 17, 18, 19, 20, 22, 23, 26, 27, 29 |
| `hpc_mixedbig` | 0,1,2 | 22 |
| `hpc_modal25` | 0,1,2 | 25 |
| `hpc_notb25` | 0,1,2 | 23, 27 |
| `hpc_poor25` | 0,1,2 | 27 |
| `hpc_pretrain` | 0,1,2 | 20 |
| `hpc_rand25` | 0,1,2 | 23, 24, 25, 27, 29 |
| `hpc_rdsm25` | 0,1,2 | 29 |
| `hpc_rdsr25` | 0,1,2 | 29 |
| `hpc_real25` | 0,1,2 | 22, 29 |
| `hpc_real25r_i1280` | 0,1,2 | 29 |
| `hpc_real25r` | 0,1,2 | 27, 29 |
| `hpc_real3676` | 0,1,2 | 22, 23 |
| `hpc_real50` | 0,1,2 | 22 |
| `hpc_real_only` | 0,1,2 |  |
| `hpc_realism25` | 0,1,2 | 26 |
| `hpc_rich25` | 0,1,2 | 27 |
| `hpc_v10n25` | 0,1,2 | 29 |
| `hpc_v11_25` | 0,1,2 | 29 |
| `hpc_v12e25` | 0,1,2 | 29 |
| `hpc_v13r25` | 0,1,2 | 29 |
| `hpc_v7a25` | 0,1,2 | 25, 27 |
| `hpc_v7c25` | 0,1,2 |  |
| `hpc_v7p25_i1280` | 0,1,2 | 29 |
| `hpc_v7p25` | 0,1,2 | 27, 29 |
| `hpc_v8a25` | 0,1,2 | 27, 29 |
| `hpc_v8b25` | 0,1,2 | 27, 29 |
| `hpc_v9a25` | 0,1,2 | 29 |

## Other files

`README.md`, `baseline_coco_bdd100k.json`, `baseline_coco_cityscapes.json`, `label_audit_bus.json`, `label_audit_truck.json`, `mosaic_ablation_off_bdd_quick.json`, `mosaic_ablation_on_bdd_quick.json`, `real_control_bdd100k.json`, `real_control_cityscapes.json`, `real_plus_synth_v5_bdd100k.json`, `real_plus_synth_v5_cityscapes.json`, `smoke_baseline_bdd200.json`, `smoke_ours_bdd50.json`, `smoke_peek_scratch_bdd200.json`, `synth_finetune_bdd100k.json`, `synth_finetune_cityscapes.json`, `synth_finetune_v2_bdd100k.json`, `synth_finetune_v2_bdd100k_imgsz640.json`, `synth_finetune_v2_bdd100k_scene.json`, `synth_finetune_v2_cityscapes.json`, `synth_finetune_v3_bdd100k.json`, `synth_finetune_v3_cityscapes.json`, `synth_finetune_v4a_bdd100k.json`, `synth_finetune_v4a_cityscapes.json`, `synth_finetune_v4b_bdd100k.json`, `synth_finetune_v4b_cityscapes.json`, `synth_finetune_v5_bdd100k.json`, `synth_finetune_v5_cityscapes.json`, `synth_finetune_v6_bdd100k.json`, `synth_finetune_v6_cityscapes.json`, `synth_scratch_bdd100k.json`, `synth_scratch_cityscapes.json`, `synth_scratch_v2_bdd100k.json`, `synth_scratch_v2_cityscapes.json`, `synth_scratch_v3_bdd100k.json`, `synth_scratch_v3_cityscapes.json`, `synth_scratch_v4a_bdd100k.json`, `synth_scratch_v4a_cityscapes.json`, `synth_scratch_v4b_bdd100k.json`, `synth_scratch_v4b_cityscapes.json`, `synth_scratch_v5_bdd100k.json`, `synth_scratch_v5_cityscapes.json`, `synth_scratch_v5_seed1_bdd100k.json`, `synth_scratch_v5_seed1_cityscapes.json`, `synth_scratch_v5_stylized2_bdd100k.json`, `synth_scratch_v5_stylized2_cityscapes.json`, `synth_scratch_v5_stylized2_seed1_bdd100k.json`, `synth_scratch_v5_stylized2_seed1_cityscapes.json`, `synth_scratch_v5_stylized_bdd100k.json`, `synth_scratch_v5_stylized_cityscapes.json`, `synth_scratch_v6_bdd100k.json`, `synth_scratch_v6_cityscapes.json`, `synth_scratch_v6_stylized_bdd100k.json`, `synth_scratch_v6_stylized_cityscapes.json`
