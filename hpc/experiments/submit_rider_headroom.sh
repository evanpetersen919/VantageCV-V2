#!/bin/bash
# The rider headroom check (docs/riders/headroom_check.md): 5 arms x seeds 0-2 = 15 jobs, names hpc_rider_<arm>_s<seed>.
# Same recipe for every arm (YOLOv10m from scratch, 200 epochs, AdamW fixed, imgsz 960). Run from the repository root.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
for ARM in A rare2 rare4 rand2 rand4; do
  for SEED in 0 1 2; do
    bash "$HERE/submit_rider.sh" "hpc_rider_${ARM}_s${SEED}" "$ARM" "$SEED"
  done
done
echo "Submitted 15 jobs. Check with: squeue -u \$USER"
