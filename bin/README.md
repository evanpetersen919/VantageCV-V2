# bin/

Command-line tools, run from the repository root with `PYTHONPATH=. python bin/<name>.py --help`
(the shell and PowerShell ones as named). They are grouped by purpose below; the one-line
descriptions are each script's own docstring.

These scripts are not moved into subfolders because the experiment log records the exact commands
that produced each result (`bin/<name>.py ...`), and those commands should keep working.

## Generate

| Script | What it does |
|---|---|
| `generate_dataset.py` | Command-line entry point for procedural dataset generation. |
| `generate_live_dataset.py` | Render a dataset of real UE5 frames with labels from the same camera. |
| `send_scenario_to_ue5.py` | Command-line entry point for sending one generated scenario to a live UE5 editor over the WebSocket JSON-RPC bridge. |
| `launch_ue5.ps1` | Launches the VantageCV_UE5 standalone game session the live-rendering pipeline talks to |

## Export, post-process and package

| Script | What it does |
|---|---|
| `split_dataset.py` | Split a live dataset into train and validation sets by scenario. |
| `export_yolo.py` | Write a split live dataset in the layout ultralytics trains from. |
| `export_kitti.py` | Write a KITTI-style 3D detection folder from a rendered dataset's ``annotations.json``. |
| `export_masks.py` | Write instance and semantic mask PNGs from a rendered dataset's ``annotations.json``. |
| `package_dataset.py` | Build the self-contained release folder (Kaggle layout) from a rendered and split dataset. |
| `apply_image_realism.py` | Apply the calibrated realism post-process to a whole live dataset (images only). |
| `regenerate_modal_boxes.py` | Regenerate a live dataset's annotations with modal (visible-region) occlusion boxes. |
| `stylize_backgrounds.py` | Randomize every image's background (buildings, road, sidewalk, foliage, sky) while leaving every labeled object's own pixels completely untouched. |
| `overlay_boxes_3d.py` | Draw the exported 3D ground-truth boxes over live UE5 renders, for eyeballing. |

## Audit a dataset

| Script | What it does |
|---|---|
| `audit_dataset.py` | Audit a finished live dataset: hard label checks, statistics and flagged crops. |
| `audit_labels.py` | Measure this project's geometric labels against the engine's exact ones (game running). |
| `verify_vehicle_boxes.py` | Check every vehicle ground-truth box against what the engine renders. |

## Train and evaluate a detector

| Script | What it does |
|---|---|
| `train_detector.py` | Train a YOLOv10 detector on the exported synthetic dataset (needs PyTorch + ultralytics). |
| `evaluate_detector.py` | Score a detector on a real benchmark (needs PyTorch + ultralytics). |
| `score_weights.sh` | Score trained weights on the real benchmarks, on this machine (no training). |
| `analyze_runs.py` | Summarize repeated runs and compare arms (mean, spread, Welch t-test). |
| `box_outcomes.py` | Per real ground-truth box of each class: did a trained detector find it, mislabel it, find it only at low confidence, or miss it? (needs PyTorch + ultralytics) |
| `summarise_box_outcomes.py` | Summarise per-box outcomes of trained arms over seeds (reading rule: hpc/README.md section 16). |
| `gradcam_compare.py` | Grad-CAM overlays for a YOLOv10m checkpoint, on a fixed real-image panel. |
| `prepare_rider_headroom.py` | Build the datasets of the rider headroom check: how much does more real rare-class data help? |
| `prepare_real_control.py` | Build the real-data control dataset: real BDD100K *training* images in YOLO format. |
| `select_realdrivesim.py` | Choose 512 RealDriveSim frames and write them as a VantageCV-style batch folder. |
| `plot_results.py` | Draw the results figures used in ``README.md`` and ``EXPERIMENT_LOG.md`` from the result files. |
| `hpc_check_data.py` | Pre-flight check for the cluster: every image and label file each data file refers to exists. |
| `hpc_make_data.py` | Build the YOLO ``data.yaml`` files for the cluster, from the uploaded dataset folders. |

## One-off calibration and measurement (their results are in the experiment log)

| Script | What it does |
|---|---|
| `calibrate_image_realism.py` | Find realism-post-process parameters by measurement, not guessing. |
| `calibrate_night.py` | Render the same scenes under several environment settings and score each against BDD100K. |
| `compare_image_stats.py` | Compare simple image statistics of rendered frames with BDD100K val frames. |
| `fit_max_annotation_distance.py` | Fit each class's ``AnnotationPolicy.max_distance_m`` against real benchmark box sizes. |
| `measure_facade_piece_bounds.py` | Measure the real bounds of every building-kit mesh the generator can place. |
| `measure_layout.py` | Measure a generator profile's scene-layout statistics without the game. |
| `measure_night_brightness.py` | Measure mean-pixel-brightness statistics for night images, synthetic and real. |
| `measure_rider_stats.py` | Measure rider, bike and motor statistics in BDD100K's detection labels. |
| `measure_pedestrian_extents.py` | Measure every City Sample pedestrian body's real extents per animation frame. |
| `measure_rig_gap.py` | Measure the gap between a tractor cab and its trailer in the engine, for several hitch offsets. |
| `measure_vehicle_bounds.py` | Measure every City Sample vehicle model's real ground-truth box and print the module source for ``src/procedural/vehicle_bounds.py``. |
| `measure_vehicle_lamps.py` | Measure every City Sample vehicle's real headlight/tail-light mesh positions and body bounds through the live UE5 RPC bridge (``GetStaticMeshBounds``), and print them as JSON -- the source data for ``src/procedural/vehicle_lamp_geometry.py``. |
| `dump_vehicle_meshes.py` | Dump the render triangles of every City Sample vehicle model to a data file. |

## Assets

| Script | What it does |
|---|---|
| `bake_riders.py` | Bake Rocketbox riders and the bicycle into static meshes and import them into the Unreal project. |
| `bake_rocketbox.py` | Bake Microsoft Rocketbox avatars into static posed meshes and import them into the Unreal project. |
