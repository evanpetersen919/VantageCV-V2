#!/bin/bash
# Do visible-part (modal) box labels help? The same v5 synthetic images, with the labels
# regenerated so a partly hidden car, truck, bus or pedestrian is boxed only where it can be seen
# (as BDD100K and Cityscapes box it), mixed with real data. Compare with the same recipe on the
# original full-extent labels: hpc_mixed25 (25% real) and hpc_adamw_mixed (100% real).
# 6 jobs, AdamW fixed. Needs data/train2000_v5_modal (see hpc/README.md).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_modal25_s$SEED"      mixed_25pct_modal "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_adamw_modal_s$SEED"  mixed_modal       "$SEED" 1.0 10
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER"
