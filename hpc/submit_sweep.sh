#!/bin/bash
# Data-efficiency sweep at one real-data fraction:   bash hpc/submit_sweep.sh 25   (or 50)
# Real-only vs real + all synthetic, three seeds each: 6 jobs. Same recipe as submit_planned.sh.
set -euo pipefail
PCT="${1:?usage: submit_sweep.sh 25|50}"
case "$PCT" in 25|50) ;; *) echo "PCT must be 25 or 50" >&2; exit 1 ;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"
for SEED in 0 1 2; do
  bash "$HERE/submit.sh" "hpc_real${PCT}_s$SEED"  "real_${PCT}pct"  "$SEED" 1.0 10
  bash "$HERE/submit.sh" "hpc_mixed${PCT}_s$SEED" "mixed_${PCT}pct" "$SEED" 1.0 10
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER"
