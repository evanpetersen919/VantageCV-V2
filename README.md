# Synthetic AV Dataset Generator

Procedural, deterministic, seed-based generation of synthetic autonomous-vehicle
perception datasets (road networks, lane topology, buildings, traffic, sensor
simulation, and ground-truth annotations), specified in
[MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md](MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md).

## Status

Phase 0 (project initialization) complete. See
[HOW_TO_USE_MASTER_PROMPT.md](HOW_TO_USE_MASTER_PROMPT.md) for the phase roadmap.

## Requirements

- Python 3.11.8
- Poetry 1.7.1 (or `pip install -r` equivalent via `pyproject.toml`)
- Unreal Engine 5.4 LTS (required starting Phase 4 — not needed for the pure-Python
  procedural generation engine in Phases 1-3)

## Setup

```bash
poetry install
poetry run pytest --cov=src tests/
```

## Project Layout

- `src/procedural/` — road network, lane topology, building placement, traffic, mesh generation (pure Python/NumPy)
- `src/ue5/` — UE5 communication layer (Phase 4+)
- `src/sensors/` — camera/LiDAR/radar models (Phase 5+)
- `src/ground_truth/` — bbox/segmentation/occlusion extraction (Phase 5+)
- `src/export/` — COCO/NuScenes exporters (Phase 6+)
- `src/validation/` — dataset sanity checks and sim2real analysis (Phase 6+)
- `src/orchestration/` — CLI-driven batch/distributed generation (Phase 6+)
- `unreal_plugin/SyntheticDataGen/` — UE5 C++ plugin skeleton (Phase 4+)
- `configs/` — scenario and sensor YAML templates
- `tests/` — unit, integration, and performance test suites
