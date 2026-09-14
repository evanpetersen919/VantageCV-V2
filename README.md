# Synthetic AV Dataset Generator

Procedural, deterministic, seed-based generation of synthetic autonomous-vehicle
perception datasets: road networks, lane topology, buildings, traffic, sensor
simulation, and ground-truth annotations, exported as COCO datasets.

See [`docs/architecture.rst`](docs/architecture.rst) (or the built Sphinx docs)
for the full system design, and [`docs/user_guide.rst`](docs/user_guide.rst)
for real, executable usage examples.

## Status

All 8 phases complete (road network → lanes → buildings → traffic → meshes →
validation → sensors/ground truth → export → distributed/resumable generation →
docs). See [`docs/release_notes.rst`](docs/release_notes.rst) for what shipped in
each phase and [`KNOWN_GAPS_AND_ISSUES.md`](KNOWN_GAPS_AND_ISSUES.md) for every
deliberate scope decision and bug found along the way.

## Requirements

- Python 3.11.8
- [Poetry](https://python-poetry.org/) 1.7.1
- Unreal Engine 5.4 LTS -- only if you intend to compile/use
  `unreal_plugin/SyntheticDataGen/`, which has never been built or verified in
  this project (see `KNOWN_GAPS_AND_ISSUES.md`). Not needed for anything else
  in this repo.

## Setup

```bash
poetry install
poetry run pytest --cov=src tests/
```

If `poetry run pytest` doesn't pick up a module you just added, run
`poetry install` again first -- see `KNOWN_GAPS_AND_ISSUES.md`.

## Quick start

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
- `src/ue5/` -- JSON-RPC/WebSocket client for UE5 (tested against a local mock server)
- `unreal_plugin/SyntheticDataGen/` -- UE5 C++ plugin skeleton (never compiled -- see `KNOWN_GAPS_AND_ISSUES.md`)
- `configs/` -- scenario and sensor YAML templates (reference only -- not yet loaded by any code, see `KNOWN_GAPS_AND_ISSUES.md`)
- `docs/` -- Sphinx documentation source
- `tests/` -- unit and integration test suites
