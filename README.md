# Synthetic AV Dataset Generator

Procedural, deterministic, seed-based generation of synthetic autonomous-vehicle
perception datasets: road networks, lane topology, buildings, traffic, sensor
simulation, and ground-truth annotations, rendered live through a real UE5.4
game (City Sample assets) and exported as COCO datasets with 2D boxes,
segmentation, occlusion/truncation, and per-scenario condition metadata
(season, weather, time of day).

See [`docs/architecture.rst`](docs/architecture.rst) (or the built Sphinx docs)
for the full system design, and [`docs/user_guide.rst`](docs/user_guide.rst)
for real, executable usage examples.

## What the generator produces

Every object is placed and tracked as a real 3D box (center, dimensions,
heading) -- that 3D geometry is what drives occlusion ray-casting and 2D
projection, and every generated frame's QA overlay draws it directly (yellow
wireframe below) alongside the exported 2D box (white) and segmentation
silhouette (cyan), so the two stay honestly checkable against each other:

![A whole generated city block from directly above, with 3D wireframe boxes on every building and vehicle, plus their 2D projected boxes](docs/images/city_overview_2d_3d_boxes.jpg)

Only the 2D box and segmentation polygon are written into the exported COCO
dataset today -- the 3D boxes stay internal-only for now (no LiDAR point
clouds are generated yet to pair them with; see
[`KNOWN_GAPS_AND_ISSUES.md`](KNOWN_GAPS_AND_ISSUES.md)). Boxes are shrunk to
the visible region for partially-occluded objects (matching BDD100K/
Cityscapes' own annotation convention -- see
[`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md)):

![Bounding boxes and segmentation polygons on a live-rendered night/rain scene](docs/images/segmentation_and_bbox_example.jpg)

Season, weather and time-of-day are drawn per scenario from real conditions
data (see `src/procedural/environment.py`), so one dataset run naturally spans
a wide range of real-world driving conditions in the same set of city layouts:

![Four scenes from the same generator run: clear day, night rain, overcast day, and clear day with a garbage truck](docs/images/scene_diversity_labels.jpg)

## Status

The core procedural pipeline (road network → lanes → buildings → traffic →
meshes → validation → sensors/ground truth → export → distributed/resumable
generation → docs) is complete, plus follow-on additions beyond MASTER_PROMPT's
own roadmap (vehicle/pedestrian placement, a real CLI + YAML config loader,
per-lane turn connectivity, an opt-in sensor noise model, spatial
acceleration for LiDAR/depth/segmentation, building types/materials,
configurable road setback, and gable roofs for residential buildings). See
[`docs/release_notes.rst`](docs/release_notes.rst) for what shipped in each
phase/addition and [`KNOWN_GAPS_AND_ISSUES.md`](KNOWN_GAPS_AND_ISSUES.md)
for every deliberate scope decision and bug found along the way.

`unreal_plugin/SyntheticDataGen/` is built, compiled and the primary way real
datasets get rendered: a WebSocket JSON-RPC bridge (`src/ue5/backend.py`)
drives a live UE5 game session (`bin/generate_live_dataset.py`) that spawns
each scenario's actual City Sample geometry, vehicles and pedestrians, then
captures and labels the frame.

### Ongoing: sim-to-real transfer experiment

A live-rendered synthetic dataset trained YOLOv10m detectors that transfer
poorly to real photos (BDD100K, Cityscapes) so far. [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md)
tracks every training run, what changed, the measured real-benchmark results,
and a full evidence-based diagnostic pass (pixel statistics, Grad-CAM, label
convention research, rendering-pipeline audit) -- an honest, in-progress
research log, not a highlight reel.

## Requirements

- Python 3.11.8
- [Poetry](https://python-poetry.org/) 1.7.1
- Unreal Engine 5.4 LTS -- required for `bin/generate_live_dataset.py` (the
  real rendering path) and for building `unreal_plugin/SyntheticDataGen/`
  against a City Sample-based UE5 project. Not needed for the offline
  procedural generation path (`bin/generate_dataset.py`, no live game).

## Setup

```bash
poetry install
poetry run pytest --cov=src tests/
```

If `poetry run pytest` doesn't pick up a module you just added, run
`poetry install` again first -- see `KNOWN_GAPS_AND_ISSUES.md`.

## Quick start

Command line, using one of the two real (`urban_dense`/`urban_sparse`)
scenario templates under `configs/scenario_templates/`:

```bash
python bin/generate_dataset.py \
    --config configs/scenario_templates/urban_dense.yaml \
    --num-scenarios 10 \
    --base-seed 0 \
    --bounds -250 -250 250 250 \
    --output-dir ./datasets/synthetic_v1
```

Or directly from Python:

```python
from src.procedural.scenario import ScenarioType, ScenarioTypeConfig
from src.orchestration.dataset_generator import generate_dataset
from pathlib import Path

config = ScenarioTypeConfig(
    scenario_type=ScenarioType.URBAN_DENSE,
    avg_block_size=(100.0, 150.0),
    avg_road_width=12.0,
    num_intersections=(4, 9),
    intersection_types=["4way", "3way"],
    building_density=0.8,
    building_heights=(20.0, 40.0),
    traffic_density=(0.6, 1.0),
    vehicle_mix={"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05},
    complexity_score=80,
)

result = generate_dataset(
    num_scenarios=10,
    base_seed=0,
    config=config,
    bounds=(-250.0, -250.0, 250.0, 250.0),
    output_dir=Path("./datasets/synthetic_v1"),
)
```

See [`docs/user_guide.rst`](docs/user_guide.rst) for more (parallel generation
via Ray, resumable/checkpointed generation, and more) -- every example there is
a real, executed `doctest`, not untested prose.

### Live rendering (real UE5 frames)

Requires a running UE5 game session with the plugin loaded (see
`unreal_plugin/SyntheticDataGen/`), reachable over the WebSocket RPC bridge:

```bash
python bin/generate_live_dataset.py \
    --config configs/scenario_templates/urban_dense.yaml \
    --num-scenarios 20 \
    --seed 0 \
    --out ./live_dataset/my_run
```

Runs a camera self-check against four known ground squares before rendering
anything, and resumes cleanly if the game crashes mid-run (rerun the same
command). See [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md) for how this path is
actually used end-to-end (dataset generation → YOLO training → real-benchmark
evaluation).

## Building the docs

```bash
poetry run sphinx-build -b html docs docs/_build/html
```

## Project layout

- `src/procedural/` -- road network, lane topology, building placement, traffic, mesh generation
- `src/sensors/` -- camera/LiDAR models
- `src/ground_truth/` -- bbox/segmentation/depth-map extraction
- `src/export/` -- COCO exporter, metadata aggregation
- `src/validation/` -- dataset sanity checks
- `src/orchestration/` -- end-to-end pipeline, Ray-based parallel generation, resumable/checkpointed generation
- `src/ue5/` -- JSON-RPC/WebSocket client for UE5, driving a live game session
- `unreal_plugin/SyntheticDataGen/` -- UE5 C++ plugin: scenario loading, mesh spawning, night lights, RPC server (built and in active use)
- `configs/` -- scenario and sensor YAML templates (`urban_dense`/`urban_sparse` are real and loadable via `src/utils/config_loader.py`; the other three are reference-only, see `KNOWN_GAPS_AND_ISSUES.md`)
- `bin/generate_dataset.py` -- offline procedural generation, no live game
- `bin/generate_live_dataset.py` -- real UE5 rendering, the primary path for actual training data
- `bin/train_detector.py`, `bin/evaluate_detector.py` -- YOLO training and real-benchmark (BDD100K/Cityscapes) evaluation for the sim-to-real experiment
- `EXPERIMENT_LOG.md` -- every training run in that experiment: what changed, why, and the measured results
- `docs/` -- Sphinx documentation source
- `tests/` -- unit and integration test suites
