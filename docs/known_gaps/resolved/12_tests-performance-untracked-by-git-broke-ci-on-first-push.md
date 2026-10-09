### [RESOLVED] `tests/performance/` untracked by git — broke CI on first push
Phase 0's `.gitkeep`-placeholder pass (adding placeholders so empty
scaffold directories survive git, which doesn't track empty dirs) missed
`tests/performance/`. It existed on local disk the whole time — created
during scaffolding and never deleted — so every local test run before this
found it and passed, masking the problem entirely. A fresh `git clone`
(exactly what GitHub Actions does) never had it, so
`test_required_directory_exists[tests/performance]` failed there, which
surfaced as the "Lint and Test / test" check going red on the first push
(commit `a70a381`) while "lint" passed. Fixed by adding
`tests/performance/.gitkeep` (commit `fefdccc`) and verifying by cloning
the repo to a clean temp directory and re-running the exact CI command
(`poetry run pytest --cov=src --cov-report=xml --cov-fail-under=90
tests/`) before pushing — confirmed 69/69 pass there before trusting it.
**Process takeaway**: "tests pass locally" is not sufficient evidence for
a scaffold/structure test suite when the working tree has accumulated
directories across a session — a local run can pass on stale disk state
that git never actually captured. From here on, verify state-sensitive
test suites (anything checking file/directory existence) against a fresh
clone, not just the in-place working tree, before pushing.

