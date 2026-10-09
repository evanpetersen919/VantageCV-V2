### [RESOLVED] Bare `poetry run pytest` doesn't discover brand-new source files until `poetry install` is re-run — found in Phase 5
Confirmed by direct, repeated testing: after adding a new file under
`src/` (e.g. `src/sensors/camera_model.py`), `poetry run pytest
tests/unit/test_camera_model.py` failed with `ModuleNotFoundError: No
module named 'src.sensors.camera_model'`, even though `.venv/Scripts/
python.exe -m pytest` (same venv, same test) and `poetry run python -m
pytest` both succeeded immediately. Existing (previously-added) test
files were unaffected by bare `poetry run pytest` -- only brand-new
modules triggered it. Root cause not fully diagnosed (something about how
the `pytest.exe` console-script entry point resolves the editable
install's package contents differs from `python -m pytest`), but running
`poetry install` again reliably fixed it every time it was tried.
**Action**: run `poetry install` after adding any new file under `src/`,
before trusting a bare `poetry run pytest` run of tests that import it.
`python -m pytest` (or `poetry run python -m pytest`) appears unaffected
and can be used as a workaround if `poetry install` is inconvenient.

