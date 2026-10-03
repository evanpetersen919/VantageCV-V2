#!/bin/bash
# Score trained weights on the real benchmarks, on this machine (no training).
#   bash bin/score_weights.sh WEIGHTS_ROOT NAME [NAME...]
# WEIGHTS_ROOT holds <name>/weights/best.pt (for example runs copied back from the cluster).
# Writes results/<name>_bdd100k.json and results/<name>_cityscapes.json with the same settings
# as hpc/run_arm.sbatch. Skips a benchmark whose result file already exists.
set -uo pipefail
ROOT="$1"; shift
PY=".venv-train/Scripts/python.exe"
export PYTHONPATH=.
for NAME in "$@"; do
  W="$ROOT/$NAME/weights/best.pt"
  [ -f "$W" ] || { echo "no weights: $W"; continue; }
  if [ ! -f "results/${NAME}_bdd100k.json" ]; then
    echo "=== $NAME: BDD100K ==="
    $PY bin/evaluate_detector.py --weights "$W" --class-space ours --benchmark bdd100k \
      --labels /f/datasets/bdd100k/labels/100k/val --images /f/datasets/bdd100k/images/100k/val \
      --imgsz 960 --conf 0.001 --iou 0.6 --max-det 100 --device 0 \
      --out "results/${NAME}_bdd100k.json" || echo "FAILED $NAME bdd100k"
  fi
  if [ ! -f "results/${NAME}_cityscapes.json" ]; then
    echo "=== $NAME: Cityscapes ==="
    $PY bin/evaluate_detector.py --weights "$W" --class-space ours --benchmark cityscapes \
      --cityscapes-root /f/datasets/cityscapes --imgsz 960 --conf 0.001 --iou 0.6 --max-det 100 \
      --device 0 --out "results/${NAME}_cityscapes.json" || echo "FAILED $NAME cityscapes"
  fi
done
echo "SCORING DONE"
