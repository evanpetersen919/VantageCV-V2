#!/bin/bash
# Evaluate trained arms that have weights but no result files (no retraining).
#   bash hpc/submit_eval.sh                 # every run under $HPC_ROOT/runs missing its results
#   bash hpc/submit_eval.sh NAME [NAME...]  # only these
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
if [ "$#" -gt 0 ]; then NAMES=("$@"); else
  NAMES=(); for d in "$HPC_ROOT"/runs/hpc_*; do NAMES+=("$(basename "$d")"); done
fi
COUNT=0
for NAME in "${NAMES[@]}"; do
  if [ ! -f "$HPC_ROOT/runs/$NAME/weights/best.pt" ]; then echo "skip $NAME (no best.pt)"; continue; fi
  if [ -f "$HPC_ROOT/results/${NAME}_bdd100k.json" ] && [ -f "$HPC_ROOT/results/${NAME}_cityscapes.json" ]; then
    echo "skip $NAME (already scored)"; continue; fi
  ARGS=(--partition "$SLURM_PARTITION" --gres "$SLURM_GRES" --cpus-per-task "$SLURM_CPUS"
        --mem "$SLURM_MEM" --time "${EVAL_TIME:-03:00:00}" --job-name "eval_$NAME" --chdir "$HPC_ROOT/logs")
  [ -n "$SLURM_ACCOUNT" ] && ARGS+=(--account "$SLURM_ACCOUNT")
  sbatch "${ARGS[@]}" --export=ALL,HPC_CONFIG="$HERE/config.env",NAME="$NAME" "$HERE/eval_arm.sbatch"
  COUNT=$((COUNT+1))
done
echo "Submitted $COUNT evaluation jobs. Check with: squeue -u \$USER"
