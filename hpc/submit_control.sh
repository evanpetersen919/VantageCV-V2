#!/bin/bash
# The data-volume control: real-only with 3,676 images (the same count as real + synthetic),
# three seeds. Needs bdd100k_control_extra in $HPC_ROOT/data (see hpc/README.md). Same recipe as
# submit_planned.sh, so the numbers compare directly.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_real3676_s$SEED" real_3676 "$SEED" 1.0 10
done
echo "Submitted 3 jobs. Check with: squeue -u \$USER"
