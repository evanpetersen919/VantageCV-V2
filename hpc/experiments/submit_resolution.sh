#!/bin/bash
# Resolution test: does a larger image size recover the small boxes? Real-only (460 real images) and
# real + the v7p synthetic batch, both at imgsz 1280 instead of 960 (training and evaluation), AdamW,
# 3 seeds each: 6 jobs. Compare each with the 960 arm of the same data (hpc_real25r, hpc_v7p25).
# A 1280 run needs about 1.8x the GPU memory and time of a 960 run; if a job runs out of memory, rerun it
# with BATCH=4 (ultralytics accumulates to the same nominal batch of 64).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW IMGSZ=1280
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_real25r_i1280_s$SEED" "real_25pct" "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_v7p25_i1280_s$SEED" "mixed_25pct_v7p" "$SEED" 1.0 10
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER"
