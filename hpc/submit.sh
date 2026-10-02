#!/bin/bash
# Submit one arm.   bash hpc/submit.sh NAME DATA SEED MOSAIC CLOSE [EPOCHS] [WEIGHTS]
#   DATA is one of: synth_v5 | real_control | mixed_real_v5
# Example (quick smoke test, 2 epochs):  bash hpc/submit.sh smoke real_control 0 1.0 10 2
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
NAME="$1"; DATA="$2"; SEED="$3"; MOSAIC="$4"; CLOSE="$5"; EPOCHS="${6:-200}"; WEIGHTS="${7:-yolov10m.yaml}"
ARGS=(--partition "$SLURM_PARTITION" --gres "$SLURM_GRES" --cpus-per-task "$SLURM_CPUS"
      --mem "$SLURM_MEM" --time "$SLURM_TIME" --job-name "$NAME" --chdir "$HPC_ROOT/logs")
[ -n "$SLURM_ACCOUNT" ] && ARGS+=(--account "$SLURM_ACCOUNT")
sbatch "${ARGS[@]}" \
  --export=ALL,HPC_CONFIG="$HERE/config.env",NAME="$NAME",DATA="$DATA",SEED="$SEED",MOSAIC="$MOSAIC",CLOSE="$CLOSE",EPOCHS="$EPOCHS",WEIGHTS="$WEIGHTS" \
  "$HERE/run_arm.sbatch"
