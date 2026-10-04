#!/bin/bash
# The two v7 batches rendered with the current generator (dry roads, tractor-trailer rigs), same
# seeds 70000-70255 as train_v7a, 25% real, AdamW, 3 seeds each. 6 jobs. Compare with hpc_rand25
# (the old generator), hpc_v7a25 (the first v7 batch) and each other:
#   c: v7 as it is now           (c vs a: what the road and rig fixes did)
#   p: v7 with the v6 pedestrian density (p vs c: what more pedestrians do)
# Pass c or p to submit only that batch.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export OPTIMIZER=AdamW
for LETTER in "${@:-c p}"; do
  for L in $LETTER; do
    for SEED in 0 1 2; do
      bash "$HERE/submit.sh" "hpc_v7${L}25_s$SEED" "mixed_25pct_v7$L" "$SEED" 1.0 10
    done
  done
done
echo "Submitted jobs. Check with: squeue -u \$USER"
