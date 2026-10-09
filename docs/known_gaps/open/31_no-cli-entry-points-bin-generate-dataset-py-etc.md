### [RESOLVED] No CLI entry points (`bin/generate_dataset.py` etc.)
Was: every capability this pipeline has was only reachable by importing
the Python API directly, not via a command-line tool.

Resolved by `bin/generate_dataset.py`: an argparse wrapper around
`src.orchestration.dataset_generator.generate_dataset`, using the
`config_loader.py` entry above for its `--config` flag. Handles the two
sys.path gotchas real `bin/` scripts hit in a `src`-layout project: it
inserts the repo root onto `sys.path` before importing `src.*` (running a
script directly puts the script's own directory on `sys.path`, not the
repo root or cwd), and it catches `FileNotFoundError`/`NotImplementedError`/
`ValueError` around config loading and generation to print a clean
one-line message on stderr and exit 1, rather than a raw traceback for
every-day failure modes (bad config path, unsupported scenario type,
`ScenarioValidator` failure). `scripts/run_linter.sh` and
`lint_and_test.yml` both extended to run pylint/mypy against `bin/` too,
not just black/isort as before -- it's real code now.

The other four `bin/*.py` scripts MASTER_PROMPT's Phase 0 file tree lists
(`validate_dataset.py`, `profile_performance.py`, `visualize_scenarios.py`,
`compare_sim2real.py`) still don't exist -- none of them wrap an existing
standalone capability this codebase has (there's no sim2real comparison
logic to expose a CLI for, for instance; see the Sim2real entry above).
Building them now would mean inventing functionality, not exposing
something real, so they're left deferred rather than stubbed out.

A dedicated `documentation.yml` CI workflow (also in MASTER_PROMPT's file
tree) was deliberately not built: `tests/integration/test_docs_build.py`
already runs both the HTML and doctest Sphinx builds as part of the
existing `lint_and_test.yml` `test` job, so a separate workflow would
duplicate that coverage without adding any -- the only thing it could add
(publishing built HTML docs somewhere, e.g. GitHub Pages) wasn't asked
for and needs a deliberate hosting decision, not just a workflow file.

`config_loader.py`'s `import yaml` needed a `mypy --strict` override
(`pyproject.toml`'s `[[tool.mypy.overrides]] module = "yaml.*"`, same
pattern as the pre-existing scipy override): `pyyaml` 6.0.1 ships no
`py.typed` marker, and a real `types-PyYAML` stub package exists but
adding it as a dependency would need regenerating `poetry.lock` via
`poetry lock`, which isn't possible in every environment this project is
built in (see the "Poetry install/lint/test flow" entry below). Revisit
if/when a real Poetry install is confirmed available.

