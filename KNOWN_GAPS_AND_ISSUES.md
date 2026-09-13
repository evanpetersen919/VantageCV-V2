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

### [DEFERRED] Docker/Kubernetes deployment (MASTER_PROMPT Section 2.4) not started
Not needed until Phase 6+ distributed/cloud scaling. No action needed yet.

### [DEFERRED] Sphinx documentation site (`docs/`) is an empty directory with only `.gitkeep`
MASTER_PROMPT 3.1.3 lists `docs/conf.py`, `index.rst`, etc. Deferred to
Phase 8 (Documentation & Release) per the roadmap — premature to scaffold
Sphinx before there's any API surface to document.

### [BLOCKER-for-later] Delaunay-based `RoadNetworkGenerator` cannot handle (near-)collinear node layouts — breaks the Highway scenario category
Discovered while chasing a coverage gap in Phase 1: `scipy.spatial.Delaunay`
raises `QhullError` ("Initial simplex is flat") whenever all input points are
exactly collinear, which `road_network.py::_connect_nodes` now catches and
re-raises as `ValueError` (see `test_collinear_points_raise_value_error_not_qhull_error`
in `tests/unit/test_road_network.py`).
**Why this matters**: MASTER_PROMPT Section 1.3 Category 3 (Highway) is
explicitly defined as "only parallel edges (no intersections)" — i.e.
nodes laid out in straight lines. The current grid-perturbation step adds
Gaussian noise that makes *exact* collinearity astronomically unlikely, so
generic urban-style bounds/config won't hit this — but a straight highway
segment's own generation logic (not yet written; belongs later in Phase 1
scenario-type-specific generation or Phase 2) will need either (a) a
non-Delaunay connectivity strategy for parallel/highway layouts, or (b) a
guaranteed transverse jitter large enough to keep Qhull's simplex
non-degenerate while staying visually "straight."
**Action**: do not reuse generic `RoadNetworkGenerator._connect_nodes`
unmodified for `ScenarioType.HIGHWAY` without addressing this. Revisit when
implementing scenario-type-specific road generation.

### [RISK] `_find_or_create_node` is O(N) per call / O(N^2) total for grid merging
Documented in its own docstring as an acceptable tradeoff at the scenario
sizes targeted (hundreds of nodes), confirmed fine by
`test_large_scenario_performance` (2000m x 2000m bounds completes well
under the 10s budget). Revisit with a `scipy.spatial.KDTree` if/when Phase
1 performance tests are run at the "10,000+ scenarios" scale mentioned in
MASTER_PROMPT's scalability requirements, or if bounds grow past ~5km.

## Resolved

### [RESOLVED] Coverage gate now exercised against real logic — Phase 1
The Phase 0 note about `--cov-fail-under=90` only being checked against an
empty `src/` tree is stale: `road_network.py` (199 stmts) and `scenario.py`
(48 stmts) now exist, and `poetry run pytest --cov=src` reports 97% overall
(96% on road_network.py) — a real, non-vacuous pass of the 90% bar. Verified
via `poetry run pytest --cov=src --cov-report=term-missing`, not just CI.

### [RESOLVED] `ScenarioTypeConfig`/`ScenarioType` were referenced but never defined in the master prompt
MASTER_PROMPT Section 3.2.2's test fixtures construct
`ScenarioTypeConfig(...)` and Section 3.1.3's file tree lists
`src/procedural/scenario.py`, but the document never actually defines
either the `ScenarioType` enum or the `ScenarioTypeConfig` schema/fields —
a genuine gap in the spec itself, not something I overlooked. Filled in
`src/procedural/scenario.py`: a `ScenarioType` str-enum matching Section
1.3's six categories, and a pydantic `ScenarioTypeConfig` model with the
fields implied by the fixtures (`avg_block_size`, `num_intersections`,
`building_density`, `vehicle_mix`, etc.), plus validators for range
ordering, density bounds, and vehicle-mix-sums-to-1. Covered by
`tests/unit/test_scenario.py` (14 tests, 100% coverage).

### [RESOLVED] `np.random.RandomState` seed range too small for the master prompt's own test requirement — Phase 1
The master prompt's Section 3.2.2 `test_seed_coverage_edge_cases` requires
`seed=2**63-1` to work, but confirmed by direct test:
`np.random.RandomState(2**63 - 1)` raises `ValueError: Seed must be between
0 and 2**32 - 1`. This is a genuine bug in the master prompt's own
reference implementation, not a hypothetical. Fixed in
`RoadNetworkGenerator.__init__` by switching to
`np.random.Generator(np.random.PCG64(seed))`, which accepts arbitrary-size
non-negative integer seeds via `SeedSequence` while remaining fully
deterministic. Verified: `test_seed_coverage_edge_cases` now passes for
seeds `[0, 42, 12345, 2**32-1, 2**63-1]`.

### [RESOLVED] Dataclass default `__eq__` crashes on numpy-array fields — Phase 1
Confirmed by direct test: a `@dataclass` with a `numpy.ndarray` field raises
`ValueError: The truth value of an array with more than one element is
ambiguous` on `==` comparison, because the generated `__eq__` chains
per-field `==` with `and`. The master prompt's `RoadNode`/`RoadEdge`
dataclasses have `position`/`centerline` ndarray fields and a custom
`__hash__`, but don't disable the default `__eq__` — meaning any code path
that compares two instances (e.g. `in` on a list, or an assertion) would
crash. Fixed by declaring both `@dataclass(eq=False)`; identity is via
`node_id`/`edge_id` through the manual `__hash__` only, and no code path
needs value-equality on these objects.

### [RESOLVED] Node/intersection classification used raw directed-edge degree instead of road-connection count — Phase 1
Found while investigating a coverage gap (the `degree == 3` T-junction
branch was never hit by any test). Root cause: every road is always
created as a *bidirectional pair* of directed edges
(`_create_edge_pair`), so `len(incoming_edges) + len(outgoing_edges)` is
**always even** for every node — the master prompt's own
`degree == 3 -> T_JUNCTION` condition is therefore mathematically
unreachable, and its `degree >= 4 -> FOUR_WAY` condition silently
mislabels genuine 3-way intersections (which have degree 6) as four-way.
Confirmed empirically: sampling degrees across a generated network showed
only even values (4, 6, 8, 10, ...), never 3. Fixed in
`_assign_road_attributes` by classifying on `degree // 2` (the actual
number of distinct connected roads) instead of raw degree. Added
`test_three_way_junction_classified_as_t_junction` and strengthened
`test_node_types_assigned_correctly` to assert degree is always even before
halving it. This also changes `_assign_road_attributes`' lane/speed
heuristic, which used the same (buggy) raw-degree comparison for its
`start_degree >= 3` branch.

### [RESOLVED] `scipy.spatial.qhull.QhullError` import path is deprecated
`from scipy.spatial.qhull import QhullError` (used in some scipy example
code and easy to reach for) emits a `DeprecationWarning` on scipy 1.11.4 —
confirmed by direct import test. Used `from scipy.spatial import
QhullError` instead (the supported public path).

### [RESOLVED] `mypy --strict` had no path for scipy (no py.typed marker) or bare `np.ndarray` — Phase 1
scipy 1.11.4 ships no type stubs, so any module importing `scipy.spatial`
failed `--strict` with `import-untyped`. Added a `[[tool.mypy.overrides]]`
block in `pyproject.toml` scoped to `module = "scipy.*"` with
`ignore_missing_imports = true`. Separately, bare `np.ndarray` field/return
annotations failed `type-arg`; replaced with `numpy.typing.NDArray[np.float64]`
throughout `road_network.py`.

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
