#!/bin/bash
# Submit one arm of the rider headroom check.   bash hpc/submit_rider.sh NAME ARM SEED
#   ARM is one of: A | rare2 | rare4 | rand2 | rand4   (built by bin/prepare_rider_headroom.py)
# Example (quick smoke test, 2 epochs):  EPOCHS=2 bash hpc/submit_rider.sh smoke_rider A 0
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
NAME="$1"; ARM="$2"; SEED="$3"
ARGS=(--partition "$SLURM_PARTITION" --gres "$SLURM_GRES" --cpus-per-task "$SLURM_CPUS"
      --mem "$SLURM_MEM" --time "$SLURM_TIME" --job-name "$NAME" --chdir "$HPC_ROOT/logs")
[ -n "$SLURM_ACCOUNT" ] && ARGS+=(--account "$SLURM_ACCOUNT")
sbatch "${ARGS[@]}" \
  --export=ALL,HPC_CONFIG="$HERE/config.env",NAME="$NAME",ARM="$ARM",SEED="$SEED",EPOCHS="${EPOCHS:-200}" \
  "$HERE/run_rider_arm.sbatch"
