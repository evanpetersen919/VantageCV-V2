#!/bin/bash
# The v13 Rocketbox-pedestrian batch, 25% real, AdamW, 3 seeds (3 jobs). Same scenes, seeds (70000-70255), config and fleet as train_v12e, so v12e25 is the comparison:
#   r: City Sample crowd characters replaced by baked Microsoft Rocketbox avatars (MIT), labels exact in both
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_v13r25_s$SEED" "mixed_25pct_v13r" "$SEED" 1.0 10
done
echo "Submitted jobs. Check with: squeue -u \$USER"
