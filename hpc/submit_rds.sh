#!/bin/bash
# The matched comparison with RealDriveSim, 25% real, AdamW, 3 seeds each (6 jobs). Each arm adds 512 RealDriveSim
# frames to the same 25% real BDD100K images as hpc_v7p25 (which adds the 512 train_v7p frames):
#   m: frames whose person, car, bus and truck counts and night share match train_v7p (decides the rule)
#   r: 512 random frames from the same pool (reported only)
# Pass m or r to submit only that arm.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export OPTIMIZER=AdamW
for L in ${@:-m r}; do
  for SEED in 0 1 2; do
    bash "$HERE/submit.sh" "hpc_rds${L}25_s$SEED" "mixed_25pct_rds$L" "$SEED" 1.0 10
  done
done
echo "Submitted jobs. Check with: squeue -u \$USER"
