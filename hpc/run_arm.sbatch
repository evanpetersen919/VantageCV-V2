#!/bin/bash
#SBATCH --job-name=vcv
#SBATCH --output=%x_%j.log
# One training arm + its two real-benchmark evaluations. Submit with hpc/submit.sh (it sets the
# variables below and the Slurm resources from config.env).
set -euo pipefail
: "${NAME:?}" "${DATA:?}" "${SEED:?}" "${MOSAIC:?}" "${CLOSE:?}" "${HPC_CONFIG:?}"
EPOCHS="${EPOCHS:-200}"
WEIGHTS="${WEIGHTS:-yolov10m.yaml}"
# OPTIMIZER=AdamW fixes the optimizer (same settings ultralytics' "auto" uses for short runs);
# otherwise "auto" picks MuSGD or AdamW from the run length, which differs between arms.
IMGSZ="${IMGSZ:-960}"   # training and evaluation image size (960 for every arm before the resolution test)
OPT_ARGS=""
[ -n "${OPTIMIZER:-}" ] && OPT_ARGS="--optimizer $OPTIMIZER --lr0 0.00125 --momentum 0.9 --warmup-bias-lr 0.0"

source "$HPC_CONFIG"
[ -f "$(dirname "$HPC_CONFIG")/config.local.env" ] && source "$(dirname "$HPC_CONFIG")/config.local.env"
for m in $MODULES; do module load "$m"; done
source "$HPC_ROOT/venv/bin/activate"
cd "$HPC_ROOT/repo"
export PYTHONPATH=.

# Copy the training data to node-local scratch when the node offers it (shared filesystems are slow
# with thousands of small images), and regenerate the data files to point there.
LOCAL="${SLURM_TMPDIR:-${TMPDIR:-}}"
if [ -n "$LOCAL" ] && [ -d "$LOCAL" ]; then
  # One folder per job: jobs on the same node share /tmp, and a shared folder made parallel jobs
  # collide. It is removed when the job ends, so six jobs cannot fill the node's disk.
  SCRATCH="$LOCAL/vcv-${SLURM_JOB_ID:-$$}"
  trap 'rm -rf "$SCRATCH"' EXIT
  mkdir -p "$SCRATCH/data" "$SCRATCH/yaml"
  cp -r "$HPC_ROOT/data/train2000_v5" "$HPC_ROOT/data/bdd100k_control" "$SCRATCH/data/"
  # A data folder the arm needs but the cluster lacks must stop the job: skipping it silently once
  # left the yaml files unwritten and failed six jobs with a confusing "yaml does not exist".
  copy_required() {
    [ -d "$HPC_ROOT/data/$1" ] || { echo "ERROR: $HPC_ROOT/data/$1 is missing (needed by $DATA)" >&2; exit 1; }
    cp -r "$HPC_ROOT/data/$1" "$SCRATCH/data/"
  }
  [ -d "$HPC_ROOT/data/bdd100k_control_extra" ] && cp -r "$HPC_ROOT/data/bdd100k_control_extra" "$SCRATCH/data/"
  [[ "$DATA" == *_big || "$DATA" == *_notb || "$DATA" == *_rand || "$DATA" == *_poor || "$DATA" == *_rich ]] && copy_required train2000_v5b
  [[ "$DATA" == *_realism ]] && copy_required train2000_v5_realism
  [[ "$DATA" == *_modal ]] && copy_required train2000_v5_modal
  [[ "$DATA" == *_v7[acp] || "$DATA" == *_v8[ab] || "$DATA" == *_v9a || "$DATA" == *_v10n || "$DATA" == *_v11 || "$DATA" == *_v12e || "$DATA" == *_v13r || "$DATA" == *_rds[mr] ]] && copy_required "train_${DATA##*_}"
  python bin/hpc_make_data.py --root "$SCRATCH/data" --out "$SCRATCH/yaml"
  YAML="$SCRATCH/yaml/$DATA.yaml"
else
  YAML="$HPC_ROOT/yaml/$DATA.yaml"
fi

echo "=== $NAME: training (seed $SEED, mosaic $MOSAIC, close-mosaic $CLOSE, $EPOCHS epochs) ==="
python bin/train_detector.py --data "$YAML" --weights "$WEIGHTS" --name "$NAME" \
  --project "$HPC_ROOT/runs" --epochs "$EPOCHS" --imgsz "$IMGSZ" --batch "${BATCH:-8}" --seed "$SEED" \
  --workers 4 --mosaic "$MOSAIC" --close-mosaic "$CLOSE" $OPT_ARGS

echo "=== $NAME: BDD100K ==="
python bin/evaluate_detector.py --weights "$HPC_ROOT/runs/$NAME/weights/best.pt" \
  --class-space ours --benchmark bdd100k \
  --labels "$HPC_ROOT/data/bdd100k/labels/100k/val" --images "$HPC_ROOT/data/bdd100k/images/100k/val" \
  --imgsz "$IMGSZ" --conf 0.001 --iou 0.6 --max-det 100 --device 0 \
  --out "$HPC_ROOT/results/${NAME}_bdd100k.json"

echo "=== $NAME: Cityscapes ==="
python bin/evaluate_detector.py --weights "$HPC_ROOT/runs/$NAME/weights/best.pt" \
  --class-space ours --benchmark cityscapes --cityscapes-root "$HPC_ROOT/data/cityscapes" \
  --imgsz "$IMGSZ" --conf 0.001 --iou 0.6 --max-det 100 --device 0 \
  --out "$HPC_ROOT/results/${NAME}_cityscapes.json"

echo "=== $NAME: ALL DONE ==="
