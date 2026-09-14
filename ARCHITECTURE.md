# Architecture

See [`docs/architecture.rst`](docs/architecture.rst) (or the built Sphinx docs) for
the current, accurate architecture description, kept in sync with what's actually
implemented (Phases 0-7 complete). This file is a short pointer, not a duplicate --
duplicating it here would just drift out of sync again, the way this file's own
previous version did (it claimed every generator used `numpy.random.RandomState`,
which stopped being true in Phase 1).

This system was built against a local `MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md`
specification (kept on disk, not published in this repo -- see `.gitignore`).
Where the code and that original spec disagree, `docs/architecture.rst` and the
code win -- the spec is the original ask, not always an accurate description of
what exists today. See [`KNOWN_GAPS_AND_ISSUES.md`](KNOWN_GAPS_AND_ISSUES.md)
for every place the two diverge and why.

## Building the docs

```bash
poetry run sphinx-build -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`.
