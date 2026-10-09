### [RESOLVED] Coverage gate now exercised against real logic — Phase 1
The Phase 0 note about `--cov-fail-under=90` only being checked against an
empty `src/` tree is stale: `road_network.py` (199 stmts) and `scenario.py`
(48 stmts) now exist, and `poetry run pytest --cov=src` reports 97% overall
(96% on road_network.py) — a real, non-vacuous pass of the 90% bar. Verified
via `poetry run pytest --cov=src --cov-report=term-missing`, not just CI.

