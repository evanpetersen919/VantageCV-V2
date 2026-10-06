#!/bin/bash
# Per-box outcomes of trained arms (no retraining): for every real BDD100K val box, was it found,
# mislabelled, found only at low confidence, or missed? Arms are given without the seed; every seed 0-2
# whose weights exist gets one job (about 10-15 minutes each):
#   bash hpc/submit_box_outcomes.sh hpc_real25r hpc_rand25 hpc_v7p25 hpc_v8a25
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
[ "$#" -gt 0 ] || { echo "usage: bash hpc/submit_box_outcomes.sh ARM [ARM...]   (arm = name without _s<seed>)" >&2; exit 1; }
COUNT=0
for ARM in "$@"; do
  for SEED in 0 1 2; do
    NAME="${ARM}_s${SEED}"
    if [ ! -f "$HPC_ROOT/runs/$NAME/weights/best.pt" ]; then echo "skip $NAME (no best.pt)"; continue; fi
    if [ -f "$HPC_ROOT/results/${NAME}_box_outcomes.json" ]; then echo "skip $NAME (already scored)"; continue; fi
    ARGS=(--partition "$SLURM_PARTITION" --gres "$SLURM_GRES" --cpus-per-task "$SLURM_CPUS"
          --mem "$SLURM_MEM" --time "${EVAL_TIME:-02:00:00}" --job-name "boxes_$NAME" --chdir "$HPC_ROOT/logs")
    [ -n "$SLURM_ACCOUNT" ] && ARGS+=(--account "$SLURM_ACCOUNT")
    sbatch "${ARGS[@]}" --export=ALL,HPC_CONFIG="$HERE/config.env",NAME="$NAME" "$HERE/box_outcomes.sbatch"
    COUNT=$((COUNT+1))
  done
done
echo "Submitted $COUNT box-outcome jobs. Check with: squeue -u \$USER"
