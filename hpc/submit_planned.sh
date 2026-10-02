#!/bin/bash
# The planned comparison, all on this cluster so every number shares hardware and library versions:
# real-only vs real + synthetic, three seeds each. Same recipe as the local real-control run
# (scratch, 200 epochs, mosaic on, close-mosaic 10). Six independent jobs; they run in parallel
# if the cluster has the GPUs free.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_real_only_s$SEED"  real_control   "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_mixed_s$SEED"      mixed_real_v5  "$SEED" 1.0 10
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER   Results appear in \$HPC_ROOT/results/"
