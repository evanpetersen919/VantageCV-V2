### [RESOLVED] `poetry install --no-root` left `import src` unresolvable in the test venv — Phase 1
Phase 0 ran `poetry install --no-root` (to skip installing the project
itself as a package, since there was no code in `src/` yet worth
installing). Once `tests/conftest.py` added a shared fixture that imports
`from src.procedural.scenario import ...`, pytest failed with
`ModuleNotFoundError: No module named 'src'` — the poetry venv never had
the project's own package installed. Fixed by running plain `poetry
install` (no `--no-root`), which installs `synthetic-av-dataset-gen`
itself in editable mode per `pyproject.toml`'s `packages = [{include =
"src"}]`. Contributors setting up fresh should use `poetry install`, not
`--no-root`, from Phase 1 onward.

