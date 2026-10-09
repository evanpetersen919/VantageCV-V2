### [DEFERRED] No real multi-node/multi-GPU scaling test; CPU-core parallelism confirmed sub-linear, root cause still open
MASTER_PROMPT Section 3.8 lists "Scaling tests (2GPU, 4GPU, 8GPU)" and
"Scaling efficiency" as a test bullet. Neither is implemented: this
environment has no GPUs and no multi-node cluster, and (more
fundamentally) this pipeline's actual workload is pure CPU/NumPy
geometry generation -- nothing in Phases 1-6 touches a GPU, so GPU-count
scaling isn't a meaningful axis for this codebase regardless of
environment.

What's implemented instead is genuine CPU-core parallelism via Ray's
local scheduler (`distributed_runner.py`). This entry's own earlier
"Action" (benchmark actual wall-clock scaling before assuming Ray
parallelism is paying off) has now been done, via real dogfooding on a
32-core machine (`generate_dataset` vs. `generate_dataset_distributed`,
same seed/config, output diffed to confirm byte-identical -- confirmed,
`images`/`annotations`/`categories` all exactly equal): 4 workers gave
1.29x speedup at 12 scenarios and 1.82x at 40; 8 workers gave 2.14x at
40. Real parallelism is genuinely happening (speedup improves with more
scenarios and more workers, and this is nowhere near CPU-starved on 32
cores), but it's well short of the 4x/8x linear ceiling the worker count
alone would suggest -- confirming the risk this entry already predicted
("per-task overhead... could dominate for cheap scenarios") with real
measurements, not just a hypothesis.
**Action**: the specific bottleneck (Ray's own per-task scheduling/IPC
overhead vs. serialization cost of each scenario's `CocoFrame` return
value vs. something else) hasn't been isolated -- would need per-task
profiling (e.g. Ray's own timeline view) to pin down before attempting
to fix. Revisit if real distributed generation at dataset scale
(thousands of scenarios, where the fixed overhead matters proportionally
less) makes this worth optimizing.

