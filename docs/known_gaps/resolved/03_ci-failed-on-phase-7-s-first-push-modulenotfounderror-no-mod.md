### [RESOLVED] CI failed on Phase 7's first push: `ModuleNotFoundError: No module named 'pkg_resources'` inside Ray — root cause confirmed via user-provided log
`main` commit `4c06f02` (Phase 7) went red on GitHub Actions' `test` job
despite passing locally against a genuinely fresh clone on this machine.
This session had no way to fetch the actual failure log itself (repo API
returned `403 Must have admin rights to Repository`, no `gh` auth
available, no Docker to reproduce Ubuntu locally) -- an initial fix
attempt (capping `ray.init(object_store_memory=...)` against the
well-known "small `/dev/shm` on CI" Ray failure mode) was applied as a
reasonable but unconfirmed hypothesis and did **not** fix it. The user
then pasted the actual CI log, which showed the real error: every
`ray.remote(...).remote()` call failed with
`ModuleNotFoundError: No module named 'pkg_resources'`, raised from deep
inside `ray/_private/pydantic_compat.py`'s unconditional
`from pkg_resources import packaging` (triggered the first time Ray sets
up its serialization context for a submitted task).
Root cause: `pkg_resources` ships as part of `setuptools`, and
`setuptools` was never declared as an explicit dependency anywhere in
this project -- it was only present by transitive/environment accident,
and evidently absent (or present without `pkg_resources`) in whatever
`setuptools` version the CI runner's poetry-managed venv actually got.
Attempting the straightforward fix (`poetry add setuptools`) made it
**worse**: it resolved to the newest available `setuptools` (84.0.0),
which -- confirmed by reproducing the exact same
`ModuleNotFoundError: No module named 'pkg_resources'` locally after that
install -- has itself now removed `pkg_resources` entirely, as part of
setuptools' own ongoing deprecation of that API (import warns "slated
for removal as early as 2025-11-30"). Fixed by pinning `setuptools<81`
(landed on 80.10.2), the last major line confirmed locally to still ship
an importable `pkg_resources` (with the deprecation warning, not an
error). Verified for real: `tests/integration/test_distributed_runner.py`
(the exact 3 tests that failed in CI) now pass locally, and the full
290-test suite plus lint/mypy all pass clean.
**Process note**: this took two attempts precisely because the first fix
was applied without ever seeing the real error -- a plausible, well-
justified guess is not a substitute for the actual log. Logged honestly
as a hypothesis at the time (see the entry that used to be here); once
the user provided the real traceback, the actual fix took one attempt.
See the two [RISK] entries above (setuptools pin fragility, Ray's own
future `pkg_resources` removal) for what could still break this later.

