# scripts/

Development tooling and research one-offs. The product CLIs are in [`bin/`](../bin/README.md).
Research scripts stay here because the experiment log records their paths.

## Development tools

| Script | What it does |
|---|---|
| `run_linter.sh` | black, isort, pylint and mypy --strict over `src/`, `tests/` and `bin/` (finds Poetry first). |
| `run_tests.sh` | `poetry run pytest` with the 90% coverage gate. |
| `setup_python_env.sh` | Phase 0: Python environment setup. See MASTER_PROMPT Section 3.1.5. |

## Research one-offs (night lamps, person realism, Rocketbox)

| Script | What it does |
|---|---|
| `calibrate_bloom.py` | Score lamp-bloom parameters against real night frames, offline, on a rendered night set. |
| `lamp_profile.py` | Per-car taillight statistics in real night frames and in ours, for calibrating lamp bloom. |
| `person_crop_realism.py` | How far are synthetic person crops from real ones? A Frechet distance on ResNet-50 features. |
| `rocketbox_bake_poses.py` | Blender script: bake static posed meshes of one Microsoft Rocketbox avatar. |
| `taillight_colour.py` | How red are the vehicle lights, and how warm is the scene, in real night frames and in ours? |
