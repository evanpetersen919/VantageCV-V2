#!/bin/bash
#SBATCH --job-name=vcv_eval
#SBATCH --output=%x_%j.log
# Scores an already-trained arm (its best.pt under $HPC_ROOT/runs/$NAME) on BDD100K and Cityscapes,
# without training. Used when a run finished training but its job failed before or during
# evaluation. Submit with hpc/submit_eval.sh.
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

echo "=== $NAME: BDD100K ==="
python bin/evaluate_detector.py --weights "$WEIGHTS" \
  --class-space ours --benchmark bdd100k \
  --labels "$HPC_ROOT/data/bdd100k/labels/100k/val" --images "$HPC_ROOT/data/bdd100k/images/100k/val" \
  --imgsz 960 --conf 0.001 --iou 0.6 --max-det 100 --device 0 \
  --out "$HPC_ROOT/results/${NAME}_bdd100k.json"

echo "=== $NAME: Cityscapes ==="
python bin/evaluate_detector.py --weights "$WEIGHTS" \
  --class-space ours --benchmark cityscapes --cityscapes-root "$HPC_ROOT/data/cityscapes" \
  --imgsz 960 --conf 0.001 --iou 0.6 --max-det 100 --device 0 \
  --out "$HPC_ROOT/results/${NAME}_cityscapes.json"

echo "=== $NAME: EVAL DONE ==="
