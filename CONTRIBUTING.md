# Contributing

Thanks for looking. This project is a research log as much as a codebase, so the most
useful contributions are usually **evidence**, not just code.

## Good ways to help

- **Reproduce or challenge a result.** Every number in
  [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md) comes from a command you can rerun. If yours
  differs, open an issue with your settings -- no result in the log has been repeated across
  seeds yet, so independent runs are genuinely valuable.
- **Pick an item from the roadmap** in the [README](README.md#roadmap), or
  from [`KNOWN_GAPS_AND_ISSUES.md`](KNOWN_GAPS_AND_ISSUES.md) (entries marked `[DEFERRED]`
  are scoped and waiting for someone).
- **Report a rendering or labeling bug** with a screenshot and the scenario seed -- generation
  is deterministic per seed, so a seed is enough to reproduce it.

## Ground rules

- **Evidence over guesses.** Values that drive generation (sizes, distances, spacings, ranges)
  should be measured or cited, with the source in a comment or the log. Say so when something
  is an estimate.
- **Implement, test, verify, then commit.** New behavior comes with a test that would fail
  without it.
- **One change per experiment where possible**, so results can be attributed. If you bundle
  changes, say so in the log entry.
- Report negative results too; they are logged, not hidden.

## Setup and checks

```bash
poetry install
poetry run pytest tests/unit          # fast unit suite
poetry run pylint src bin tests       # must score 10.00/10
poetry run mypy src bin               # strict
poetry run black --check .            # formatting
```

The pre-commit hooks run the same lint/type checks, so a commit that fails them will be
rejected locally. Training and evaluation scripts (`bin/train_detector.py`,
`bin/evaluate_detector.py`, `bin/gradcam_compare.py`) need a separate environment with
PyTorch and ultralytics -- see the docstring of `bin/train_detector.py`.

Live rendering additionally needs Unreal Engine 5.4 and the City Sample content; the
offline procedural generator (`bin/generate_dataset.py`) does not.

## Pull requests

Keep them focused, describe what you measured, and link the log entry if you added one.
Do not commit datasets, model weights, or Epic/City Sample content -- by this project's
convention those stay untracked (check Epic's license terms before sharing anything derived
from them).
