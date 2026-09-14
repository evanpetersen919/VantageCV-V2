#!/bin/bash
set -e

# Find a way to invoke Poetry: prefer `poetry` on PATH, then `python -m
# poetry`, then the known Windows system Python (as a last resort, for
# when `python` on PATH resolves to this project's own .venv instead of
# the system interpreter Poetry is actually installed against -- seen in
# this environment; see KNOWN_GAPS_AND_ISSUES.md's Poetry install entry).
WINDOWS_SYSTEM_PYTHON="C:\Users\evanp\AppData\Local\Microsoft\WindowsApps\python.exe"
if command -v poetry >/dev/null 2>&1; then
  POETRY=poetry
elif python -m poetry --version >/dev/null 2>&1; then
  POETRY="python -m poetry"
else
  POETRY="$WINDOWS_SYSTEM_PYTHON -m poetry"
fi

$POETRY run black --check src/ tests/ bin/
$POETRY run isort --check-only src/ tests/ bin/
$POETRY run pylint src/ tests/
$POETRY run mypy --strict src/
