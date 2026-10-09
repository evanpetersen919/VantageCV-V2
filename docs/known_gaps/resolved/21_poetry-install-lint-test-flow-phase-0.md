### [RESOLVED] Poetry install/lint/test flow — Phase 0
Original entry said Poetry wasn't installed and the flow was unverified.
Installed Poetry 1.7.1 via `pip install --user`, ran `poetry install`
(succeeded, `poetry.lock` generated and committed), then `poetry run pytest
--cov=src` (33/33 pass) and `scripts/run_linter.sh` (black/isort/pylint/mypy
--strict all clean, pylint 10.00/10) — all against the real Poetry-managed
environment, not just a bare pip venv.
**Residual note**: `poetry` was not on PATH after a `pip install --user` on
this Windows machine; `scripts/run_linter.sh` now falls back to
`python -m poetry` when the `poetry` executable isn't found. Contributors on
other machines should confirm `poetry` resolves normally, or rely on the
fallback.
**Update (Phase 4)**: partway through this session, `python` on PATH
started resolving to this project's own `.venv/Scripts/python.exe`
(created for early Phase 0 experimentation) instead of the system Python
that actually has Poetry installed -- so `python -m poetry` itself broke
(`No module named poetry`), even though the fallback logic above was
designed for the opposite problem (poetry missing from PATH, not python
resolving to the wrong installation). Cause not fully diagnosed (likely
some shell/session state change unrelated to this repo). Worked around by
invoking Poetry via its full system path
(`C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python.exe -m
poetry ...`) directly rather than trusting `python -m poetry`. Anyone
hitting `No module named poetry` should check `where python` first -- it
may not be the interpreter Poetry is installed against.

