#!/bin/bash
# Two follow-ups to the optimizer-controlled batch. 4 jobs, all with the optimizer fixed to AdamW.
#  1. hpc_adamw_mixed_s1: seed 1 of the 1,838 real + 1,838 synthetic arm stopped after 43 minutes
#     and its weights are undertrained; this re-runs it. The old run folder must be moved away first
#     (otherwise ultralytics writes a new folder and the evaluation would read the old weights).
#  2. hpc_realism25_s0-2: 25% real + the same v5 synthetic images after the calibrated realism
#     post-process (blur, desaturation, JPEG). Compare with hpc_mixed25 (same recipe and optimizer).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
OLD="$HPC_ROOT/runs/hpc_adamw_mixed_s1"
if [ -d "$OLD" ]; then
  echo "Move the invalid run first:  mv $OLD ${OLD}_invalid43min" >&2; exit 1
fi
export OPTIMIZER=AdamW
bash "$HERE/submit.sh" hpc_adamw_mixed_s1 mixed_real_v5 1 1.0 10
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_realism25_s$SEED" mixed_25pct_realism "$SEED" 1.0 10
done
echo "Submitted 4 jobs. Check with: squeue -u \$USER"
