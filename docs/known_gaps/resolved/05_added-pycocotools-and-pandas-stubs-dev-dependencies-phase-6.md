### [RESOLVED] Added `pycocotools` and `pandas-stubs` dev dependencies — Phase 6
`pycocotools==2.0.7` installed cleanly on Windows (pre-built wheel
available) and is used for real schema validation of COCO exports
(`test_coco_schema_valid_per_pycocotools` loads the export through the
actual reference `pycocotools.coco.COCO` parser, not just hand-written
structural checks). `pandas-stubs` was added rather than reaching for
the same `ignore_missing_imports` blanket-override pattern used for
scipy (Phase 1) -- pandas has a well-maintained stubs package, so
`sanity_checker.py`'s pandas usage gets real `mypy --strict` type
checking instead of being waved through.

