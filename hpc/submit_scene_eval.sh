#!/bin/bash
# Per-scene BDD100K scores for arms that are already trained (no retraining). Does the model fail
# on scene types (highway, residential) the generator never shows? Give arm names without the seed;
# every seed 0-2 whose weights exist is scored, one job each:
#   bash hpc/submit_scene_eval.sh hpc_real25 hpc_rand25 hpc_v7p25
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
[ "$#" -gt 0 ] || { echo "usage: bash hpc/submit_scene_eval.sh ARM [ARM...]   (arm = name without _s<seed>)" >&2; exit 1; }
COUNT=0
for ARM in "$@"; do
  for SEED in 0 1 2; do
    NAME="${ARM}_s${SEED}"
    if [ ! -f "$HPC_ROOT/runs/$NAME/weights/best.pt" ]; then echo "skip $NAME (no best.pt)"; continue; fi
    if [ -f "$HPC_ROOT/results/${NAME}_bdd100k_scene.json" ]; then echo "skip $NAME (already scored)"; continue; fi
    ARGS=(--partition "$SLURM_PARTITION" --gres "$SLURM_GRES" --cpus-per-task "$SLURM_CPUS"
          --mem "$SLURM_MEM" --time "${EVAL_TIME:-02:00:00}" --job-name "scene_$NAME" --chdir "$HPC_ROOT/logs")
    [ -n "$SLURM_ACCOUNT" ] && ARGS+=(--account "$SLURM_ACCOUNT")
    sbatch "${ARGS[@]}" --export=ALL,HPC_CONFIG="$HERE/config.env",NAME="$NAME" "$HERE/eval_scene.sbatch"
    COUNT=$((COUNT+1))
  done
done
echo "Submitted $COUNT scene-evaluation jobs. Check with: squeue -u \$USER"
