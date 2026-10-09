### [RESOLVED] `mypy --strict` had no path for scipy (no py.typed marker) or bare `np.ndarray` — Phase 1
scipy 1.11.4 ships no type stubs, so any module importing `scipy.spatial`
failed `--strict` with `import-untyped`. Added a `[[tool.mypy.overrides]]`
block in `pyproject.toml` scoped to `module = "scipy.*"` with
`ignore_missing_imports = true`. Separately, bare `np.ndarray` field/return
annotations failed `type-arg`; replaced with `numpy.typing.NDArray[np.float64]`
throughout `road_network.py`.

