# Contributing

Contributions are welcome. The most useful kind is evidence, not just code.

## Ways to help

- **Reproduce or challenge a result.** Every number in [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md)
  comes from a command you can rerun. If yours differs, open an issue with your settings.
- **Pick an open problem:** the [roadmap](README.md#roadmap), or a `[DEFERRED]` entry in
  [`KNOWN_GAPS_AND_ISSUES.md`](KNOWN_GAPS_AND_ISSUES.md).
- **Report a bug** with a screenshot and the scenario seed. Generation is deterministic per
  seed, so the seed is enough to reproduce it.

## Ground rules

- Measure or cite any value that drives generation, and say when something is an estimate.
- Add a test that fails without your change.
- Change one thing per experiment where possible, and log negative results too.

## Checks

```bash
poetry install
poetry run pytest tests/unit
poetry run pylint src bin tests   # must score 10.00/10
poetry run mypy src bin
poetry run black --check .
```

Training and evaluation scripts need a separate environment with PyTorch and ultralytics
(see `bin/train_detector.py`). Live rendering needs Unreal Engine 5.4 and the City Sample
content; the offline generator (`bin/generate_dataset.py`) does not.

Don't commit datasets, model weights, or Epic/City Sample content.
