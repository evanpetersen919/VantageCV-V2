## v5b — camera/material/asset changes ready for the v5 render (implemented, not yet rendered)

Five real, verified, evidence-backed changes landed in preparation for the next live-rendered
dataset. Each was implemented, unit-tested (own targeted tests + the full 818-test suite),
pylint-checked (10.00/10), and committed/pushed individually rather than as one batch, per
the same implement -> test -> confirm discipline the rest of this log follows:

| # | Change | Commit | Needs plugin rebuild? |
|---|---|---|---|
| 1 | Pitch jitter on ego/lot camera poses (+-3 deg, was perfectly level every frame) | `a3c737d` | No (pure Python pose math; UE5's RPC only ever took position + look-at) |
| 2 | Sidewalk material varies per city block (6 real migrated variants, was 1 fixed material everywhere) | `901cc5b` | **Yes** |
| 3 | Building wall materials gained 5 unused-but-migrated variants (brick brown, stucco khaki, metal brass, granite/limestone block) | `893ac79` | **Yes** |
| 4 | Tree species varies per scenario (Alder/Maple Red/Maple Sugar, was always birch) | `41da877` | No (trees spawn via the generic asset-path pipeline, no material tag involved) |
| 5 | **Bug fix**: `vehTruck_trailer01` (a cab-less cargo trailer) is no longer a standalone "truck" spawn option -- it was sampled 1-in-4 truck spawns, driving down the road with nothing pulling it | `f4b161a` | No (pure Python asset-pool data) |

**Before rendering v5, rebuild `unreal_plugin/SyntheticDataGen`** -- changes 2 and 3 add new
material tags (`pavement_1..5`, `brick_brown`, `stucco_khaki`, `metal_brass`,
`block_granite`, `block_limestone`) to the C++ `MaterialResolver`; without a rebuild those
tags fall back to UE5's default material (a visible, not silent, failure mode -- but still
worth doing the rebuild first).

Explicitly investigated and deliberately NOT done (no-guessing/no-fabrication reasons, not
oversights): `Kit_StreetLamp_B` (mesh exists, but its rotation offset needs live-in-editor
verification like the other 3 lamp styles got -- guessing it risks a visibly wrong-facing
lamp); the `Kit_bench_RR` bench kit (no measured real placement pattern exists for it, unlike
trees' real Epic point-cloud data); CHH building facade levels (checked -- already fully
wired, all 8 real levels L1-L8, the earlier "2 unused" note was stale). Roll jitter and
camera FOV/intrinsics randomization are also deferred: both need an actual RPC/engine
protocol change (today's bridge only ever sends camera position + look-at target, no
roll/up-vector, no FOV), a larger, separate effort from this batch.

