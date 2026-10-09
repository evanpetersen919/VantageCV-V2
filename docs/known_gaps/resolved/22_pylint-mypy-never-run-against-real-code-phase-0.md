### [RESOLVED] pylint/mypy never run against real code — Phase 0
`tests/unit/test_project_initialization.py` initially had 8 missing-docstring
warnings and one import-outside-toplevel warning (pylint score 7.56/10).
Fixed by adding a one-line docstring to every test function and moving the
`toml` import to module level. Now 10.00/10, mypy --strict clean.

