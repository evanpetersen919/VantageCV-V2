#!/bin/bash
# The pedestrian-free batch (train_v10n), 25% real, AdamW, 3 seeds (3 jobs). Same scenes, seeds
# (70000-70255), fleet and labelling cutoffs as train_v7p, with no synthetic pedestrians, so v7p25 is the
# comparison and the difference is what the crowd characters contribute.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_v10n25_s$SEED" "mixed_25pct_v10n" "$SEED" 1.0 10
done
echo "Submitted jobs. Check with: squeue -u \$USER"
