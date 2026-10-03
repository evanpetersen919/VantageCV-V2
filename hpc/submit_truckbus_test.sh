#!/bin/bash
# Do synthetic trucks and buses carry the gain? At 25% real (460 images), compare adding the
# synthetic images that contain NO truck or bus (about 510 of the 3,691) with adding the same
# number of randomly chosen synthetic images. Same real images, same count, optimizer fixed to
# AdamW. 6 jobs. Needs train2000_v5b on the cluster (it is already there for the volume test).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_notb25_s$SEED"  mixed_25pct_notb  "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_rand25_s$SEED"  mixed_25pct_rand  "$SEED" 1.0 10
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER"
