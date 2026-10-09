#!/bin/bash
# Synthetic pre-training, then fine-tuning on real images (the alternative to mixed training).
# For each seed: one synthetic-only run from scratch (200 epochs, no mosaic: the recipe used for
# every synthetic-only result), then three real-data fine-tunes from its best.pt (50 epochs, the
# project's fine-tune length) on 25%, 50% and 100% of the control's real images. Fine-tune seed k
# starts from pre-train seed k, so the large seed-to-seed spread of synthetic-only runs is carried
# into the comparison instead of hidden. Each fine-tune waits for its pre-train (Slurm dependency).
# 12 jobs. Results: hpc_ft25_s*, hpc_ft50_s*, hpc_ft100_s*, and hpc_pretrain_s* (synthetic only).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
for SEED in 0 1 2; do
  OUT=$(bash "$HERE/submit.sh" "hpc_pretrain_s$SEED" synth_v5 "$SEED" 0.0 0)
  JOB="${OUT##* }"
  WEIGHTS="$HPC_ROOT/runs/hpc_pretrain_s$SEED/weights/best.pt"
  for ARM in "ft25 real_25pct" "ft50 real_50pct" "ft100 real_control"; do
    set -- $ARM
    AFTEROK="$JOB" bash "$HERE/submit.sh" "hpc_$1_s$SEED" "$2" "$SEED" 1.0 10 50 "$WEIGHTS"
  done
done
echo "Submitted 12 jobs (3 pre-train, 9 fine-tune). Check with: squeue -u \$USER"
