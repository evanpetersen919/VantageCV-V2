#!/bin/bash
# Is it the supply of scarce-class instances that decides a supplement's value? 510 of the existing
# v5/v5b images, 25% real, AdamW, 3 seeds each, no rendering:
#   poor: chosen for few persons and trucks (about what the v7 batch supplied: ~550 persons, ~230 trucks)
#   rich: chosen for many persons, trucks and buses (~2,000 persons, ~1,800 trucks, ~245 buses)
# Compare with hpc_rand25 (random 510) and, for poor, hpc_v7a25. 6 jobs.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export OPTIMIZER=AdamW
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_poor25_s$SEED" mixed_25pct_poor "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_rich25_s$SEED" mixed_25pct_rich "$SEED" 1.0 10
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER"
