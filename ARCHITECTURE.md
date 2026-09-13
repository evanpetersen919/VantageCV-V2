# Architecture

See `MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md` Section 1 for the full
system design. Summary of layers, top to bottom:

1. **Orchestration** (`src/orchestration/`, `bin/`) — CLI entry points, batch/distributed generation.
2. **Procedural Generation Engine** (`src/procedural/`) — deterministic, seed-driven generation of road networks (PSLG + Delaunay), lane topology, building placement, traffic network, procedural meshes.
3. **Simulation Backend** (`unreal_plugin/`) — UE5.4 C++ plugin that loads generated scenarios and renders them.
4. **Sensor Layer** (`src/sensors/`) — camera/LiDAR/radar physical models.
5. **Ground Truth Extraction** (`src/ground_truth/`) — 3D/2D bounding boxes, segmentation, occlusion.
6. **Export** (`src/export/`) — COCO / NuScenes / custom format writers.
7. **Validation** (`src/validation/`) — sanity checks, distribution analysis, sim2real gap analysis.

## Core principle: deterministic generation from seed

```
seed: int64 -> RNG state -> Road Network -> Lanes -> Buildings -> Meshes -> Scene
```

Every generator class owns an isolated `numpy.random.RandomState`, never touches
global random state, and is covered by a determinism test
(`same seed -> bit-identical output`). See `QOL_RESEARCH_CHECKLIST.md` Section A.2/C.1.
