### [DEFERRED] Heavy/optional dependencies not yet in `pyproject.toml`
`open3d==0.17.0`, `ray==2.9.3`, `h5py==3.10.0`, `protobuf==4.25.1`,
`sphinx==7.2.6` + theme/mermaid ext, `py-spy`, `memory-profiler`,
`line-profiler` are specified in MASTER_PROMPT Section 2.2 but were left out
of Phase 0's `pyproject.toml` to keep the initial install fast and because
nothing in Phase 0-1 imports them.
**Needed by**: `open3d`/`h5py` — Phase 5 (sensors/ground truth); `ray` — Phase 6
distributed generation; `protobuf` — Phase 6 custom export; `sphinx*` — Phase 8
docs; profilers — whenever performance work starts.
**Action**: add to `pyproject.toml` in the phase that first imports them, then
re-run `poetry lock` and verify no version conflicts (open3d in particular has
had NumPy 2.x incompatibilities historically — must verify against pinned
NumPy 1.26.3).

