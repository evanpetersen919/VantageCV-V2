### [RESOLVED] CI workflow (`.github/workflows/lint_and_test.yml`) had never actually run on GitHub Actions
Was: written to spec and known to work locally via Poetry, but never
exercised on an actual Actions runner, with open questions about
`poetry install`/codecov behaving differently there.

Resolved since Phase 7 (see the `pkg_resources`/Ray entry below, found via
a real Actions run on commit `4c06f02`): every push since has run on
GitHub Actions and is confirmed green, including every commit through
`434378e` (CLI + config loader). This entry was left stale for several
commits after that -- a reminder to keep this file in sync with reality,
not just append to it.

