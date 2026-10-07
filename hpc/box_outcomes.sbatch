#!/bin/bash
#SBATCH --job-name=vcv_boxes
#SBATCH --output=%x_%j.log
# For every real ground-truth box (BDD100K val), did the trained arm $NAME find it, mislabel it, find it
# only at low confidence, or miss it? Writes ${NAME}_box_outcomes.json. Submit with
# hpc/submit_box_outcomes.sh.
set -euo pipefail
: "${NAME:?}" "${HPC_CONFIG:?}"

source "$HPC_CONFIG"
[ -f "$(dirname "$HPC_CONFIG")/config.local.env" ] && source "$(dirname "$HPC_CONFIG")/config.local.env"
for m in $MODULES; do module load "$m"; done
source "$HPC_ROOT/venv/bin/activate"
cd "$HPC_ROOT/repo"
export PYTHONPATH=.
mkdir -p "$HPC_ROOT/results"
WEIGHTS="$HPC_ROOT/runs/$NAME/weights/best.pt"
[ -f "$WEIGHTS" ] || { echo "no weights: $WEIGHTS" >&2; exit 1; }

echo "=== $NAME: per-box outcomes ==="
python bin/box_outcomes.py --weights "$WEIGHTS" \
  --labels "$HPC_ROOT/data/bdd100k/labels/100k/val" --images "$HPC_ROOT/data/bdd100k/images/100k/val" \
  --imgsz "${IMGSZ:-960}" --iou 0.6 --max-det 100 --device 0 \
  --out "$HPC_ROOT/results/${NAME}_box_outcomes.json"
echo "=== $NAME: BOX OUTCOMES DONE ==="
