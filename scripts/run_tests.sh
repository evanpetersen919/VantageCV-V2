#!/bin/bash
set -e
poetry run pytest --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=90 tests/
