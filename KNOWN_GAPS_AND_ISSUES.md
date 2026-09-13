# Known Gaps, Risks & Open Issues

Living log of everything deferred, unverified, or risky in this implementation,
so nothing gets silently lost between sessions/phases. Update this file whenever
a gap is discovered, deferred, or closed. Never delete a closed entry — mark it
`RESOLVED` with the phase/commit that fixed it.

Severity: **BLOCKER** (must fix before shipping) / **RISK** (works but fragile,
should fix before relying on it) / **DEFERRED** (intentionally postponed to a
later phase, tracked so it isn't forgotten).

---

## Open

### [DEFERRED] Heavy/optional dependencies not yet in `pyproject.toml`
`open3d==0.17.0`, `ray==2.9.3`, `h5py==3.10.0`, `protobuf==4.25.1`,
`sphinx==7.2.6` + theme/mermaid ext, `py-spy`, `memory-profiler`,
`line-profiler` are specified in MASTER_PROMPT Section 2.2 but were left out
of Phase 0's `pyproject.toml` to keep the initial install fast and because
nothing in Phase 0-1 imports them.
**Needed by**: `open3d`/`h5py` — Phase 5 (sensors/ground truth); `ray` — Phase 6
distributed generation; `protobuf` — Phase 6 custom export; `sphinx*` — Phase 8
docs; profilers — whenever performance work starts.
**Action**: add to `pyproject.toml` in the phase that first imports them, then
re-run `poetry lock` and verify no version conflicts (open3d in particular has
had NumPy 2.x incompatibilities historically — must verify against pinned
NumPy 1.26.3).

### [DEFERRED] UE5 C++ plugin skeleton is unverified — cannot compile locally
`unreal_plugin/SyntheticDataGen/` (`.uplugin`, `Build.cs`, module
header/cpp) is structurally standard UE5 module boilerplate but has **never
been opened in Unreal Editor or compiled**, because UE5.4 is not installed in
this environment.
**Risk**: Build.cs dependency names, module loading phase, or C++20 flag could
be subtly wrong in ways only the UE5 toolchain would catch.
**Action**: first time someone has UE5.4 LTS installed (Phase 4 per roadmap),
open the project, add this plugin, and confirm `RunUAT.sh/.bat BuildPlugin`
succeeds with zero warnings before writing any further C++.

### [DEFERRED] No actual UE5 `.uproject` / editor project created
MASTER_PROMPT 3.1.1 calls for creating the UE5 project itself via
`RunUAT.sh BuildProject`. Not done — no UE5 installed here, and an empty
`.uproject` shell has little value without the editor to validate it.
**Action**: do this as the first step of Phase 4, not before — Phases 1-3 are
pure Python and don't need it.

### [RISK] CI workflow (`.github/workflows/lint_and_test.yml`) has never actually run on GitHub Actions
Written to spec and now known to work locally via Poetry (see Resolved), but
never exercised on an actual Actions runner. First real push may still
surface issues (e.g. `poetry install` needing `--no-root` explicitly in CI,
codecov action needing a token for a private repo — this repo's visibility
has not been confirmed).
**Action**: watch the first Actions run after this commit is pushed; fix
immediately rather than letting it go red silently.

### [RISK] `pytest.ini_options` coverage gate (`--cov-fail-under=90`) has only been exercised against an empty `src/` tree (trivial 100% coverage, 0 statements)
33/33 Phase 0 tests pass with 100% coverage, but that's vacuous — no real
statements exist yet. The gate has never been tested against actual logic
where 90% is a meaningful bar.
**Action**: once Phase 1's `road_network.py` lands, confirm `--cov-fail-under=90`
actually fails the build when coverage is deliberately dropped below 90%
(a quick sanity check), not just that it passes when coverage is high.

### [DEFERRED] Docker/Kubernetes deployment (MASTER_PROMPT Section 2.4) not started
Not needed until Phase 6+ distributed/cloud scaling. No action needed yet.

### [DEFERRED] Sphinx documentation site (`docs/`) is an empty directory with only `.gitkeep`
MASTER_PROMPT 3.1.3 lists `docs/conf.py`, `index.rst`, etc. Deferred to
Phase 8 (Documentation & Release) per the roadmap — premature to scaffold
Sphinx before there's any API surface to document.

## Resolved

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

### [RESOLVED] pylint/mypy never run against real code — Phase 0
`tests/unit/test_project_initialization.py` initially had 8 missing-docstring
warnings and one import-outside-toplevel warning (pylint score 7.56/10).
Fixed by adding a one-line docstring to every test function and moving the
`toml` import to module level. Now 10.00/10, mypy --strict clean.
