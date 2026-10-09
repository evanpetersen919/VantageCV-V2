#!/bin/bash
# The v12 exact-label batch, 25% real, AdamW, 3 seeds (3 jobs). Same scenes, seeds (70000-70255),
# config and fleet as train_v7p, so v7p25 is the comparison:
#   e: every vehicle and pedestrian box, visible fraction and mask taken from the game's own render
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_v12e25_s$SEED" "mixed_25pct_v12e" "$SEED" 1.0 10
done
echo "Submitted jobs. Check with: squeue -u \$USER"
