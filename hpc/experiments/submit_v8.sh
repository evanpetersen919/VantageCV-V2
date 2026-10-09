#!/bin/bash
# The v8 truck/bus mix batches, 25% real, AdamW, 3 seeds each (6 jobs). Same seeds (70000-70255) and
# pedestrian density as train_v7p, so v7p25 is the comparison:
#   a: fewer rigs, fewer trucks and buses at night, bus share up to the real rate
#   b: a plus pickups and vans labelled truck for 20% of trucks (as BDD100K annotators did)
# Pass a or b to submit only that batch.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export OPTIMIZER=AdamW
for L in ${@:-a b}; do
  for SEED in 0 1 2; do
    bash "$HERE/submit.sh" "hpc_v8${L}25_s$SEED" "mixed_25pct_v8$L" "$SEED" 1.0 10
  done
done
echo "Submitted jobs. Check with: squeue -u \$USER"
