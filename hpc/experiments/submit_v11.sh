#!/bin/bash
# The box-truck pilot (train_v11), 25% real, AdamW, 3 seeds (3 jobs). Same scenes, seeds (70000-70255),
# mix and pedestrians as train_v8a, with 30% of trucks drawn from the Vehicle Variety Pack box truck, so
# v8a25 is the comparison (v7p25 the second one).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_v11_25_s$SEED" "mixed_25pct_v11" "$SEED" 1.0 10
done
echo "Submitted jobs. Check with: squeue -u \$USER"
