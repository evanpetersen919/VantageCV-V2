#!/bin/bash
# Re-runs the arms whose comparison was confounded by ultralytics' optimizer=auto (it picks MuSGD
# for the long runs and AdamW for the short ones), with AdamW (lr 0.00125) fixed everywhere, plus a
# real-only run with as many optimizer steps as the 3,676-image arms (400 epochs on 1,838 images).
# 15 jobs, 3 seeds each. Names start hpc_adamw_.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_adamw_mixed_s$SEED"      mixed_real_v5   "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_adamw_real3676_s$SEED"   real_3676       "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_adamw_mixed25big_s$SEED" mixed_25pct_big "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_adamw_mixedbig_s$SEED"   mixed_big       "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_adamw_real400_s$SEED"    real_control    "$SEED" 1.0 10 400
done
echo "Submitted 15 jobs. Check with: squeue -u \$USER"
