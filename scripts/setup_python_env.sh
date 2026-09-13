#!/bin/bash
set -e

# Phase 0: Python environment setup. See MASTER_PROMPT Section 3.1.5.
python3 --version
pip install --upgrade pip
pip install poetry==1.7.1
poetry install
poetry run pre-commit install 2>/dev/null || true
echo "Python environment ready."
