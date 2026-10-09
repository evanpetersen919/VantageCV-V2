### [RESOLVED] Root `ARCHITECTURE.md` was stale — Phase 8
Written in Phase 0, before `RoadNetworkGenerator` switched from
`numpy.random.RandomState` to `numpy.random.Generator`/`PCG64` (Phase 1,
to support the master prompt's own `2**63-1` seed test requirement).
`ARCHITECTURE.md` still claimed every generator used `RandomState`,
silently wrong since Phase 1. Replaced with a short pointer to the new
`docs/architecture.rst`, which reflects the system as actually built
across all 7 completed phases (and is far more likely to be kept current
going forward, since it's part of the Sphinx build every push now
implicitly re-checks via `test_docs_build.py`).

