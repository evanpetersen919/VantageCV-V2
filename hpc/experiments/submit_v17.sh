#!/bin/bash
# The v17 batch (scanned street trees and shrubs, lawn planting, signals), 25% real, AdamW, 3 seeds (3 jobs).
# Same scene seeds (70000-70255), split and Rocketbox crowd as train_v13r, so v13r25 is the comparison
# (rules: docs/experiments/36, fixed before any result):
#   v17: leafy photographic trees, shrubs on grass, traffic-light states; everything else as v13r
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_v17_25_s$SEED" "mixed_25pct_v17" "$SEED" 1.0 10
done
echo "Submitted jobs. Check with: squeue -u \$USER"
