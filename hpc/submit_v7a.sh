#!/bin/bash
# The first v7-generator batch (512 images: visible-part labels, v7 fleet, calibrated night, hood,
# pedestrian density, ego views) at 25% real. Compare with hpc_rand25: the same number of images
# (970 vs 972 training images), AdamW, from the earlier generator. 3 jobs.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_v7a25_s$SEED" mixed_25pct_v7a "$SEED" 1.0 10
done
echo "Submitted 3 jobs. Check with: squeue -u \$USER"
