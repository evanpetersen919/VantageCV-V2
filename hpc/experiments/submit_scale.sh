#!/bin/bash
# Synthetic-volume test: real data + BOTH synthetic batches (v5 and v5b, 3,691 images), three seeds,
# at 25% and 100% of the real images. Compare with the same real fractions + only v5 (1,838
# synthetic): if the gain over real-only grows, more synthetic data helps. Needs train2000_v5b in
# $HPC_ROOT/data (see hpc/README.md). 6 jobs, same recipe as submit_planned.sh.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_mixed25big_s$SEED" mixed_25pct_big "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_mixedbig_s$SEED"   mixed_big       "$SEED" 1.0 10
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER"
