#!/bin/bash
# The v9 distance-cutoff batch, 25% real, AdamW, 3 seeds (3 jobs). Same scenes, seeds (70000-70255)
# and fleet as train_v7p, so v7p25 is the comparison:
#   a: trucks labelled out to 95 m and buses to 72 m (v7p: 53 m and 41 m), so small trucks exist
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_v9a25_s$SEED" "mixed_25pct_v9a" "$SEED" 1.0 10
done
echo "Submitted jobs. Check with: squeue -u \$USER"
