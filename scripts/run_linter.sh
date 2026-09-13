#!/bin/bash
set -e

# Use `poetry` if it's on PATH, otherwise fall back to `python -m poetry`
# (pip --user installs on Windows often land outside PATH). See
# KNOWN_GAPS_AND_ISSUES.md for the underlying environment note.
if command -v poetry >/dev/null 2>&1; then
  POETRY=poetry
else
  POETRY="python -m poetry"
fi

$POETRY run black --check src/ tests/ bin/
$POETRY run isort --check-only src/ tests/ bin/
$POETRY run pylint src/ tests/
$POETRY run mypy --strict src/
