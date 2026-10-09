#!/bin/bash
#SBATCH --job-name=vcv-rider
#SBATCH --output=%x_%j.log
# One arm of the rider headroom check (docs/riders/headroom_check.md): train on one of the datasets built by
# bin/prepare_rider_headroom.py, then score BDD100K and Cityscapes with the rider class profile.
# Submit with hpc/submit_rider.sh. NOT YET RUN on a cluster: the data handling below is new.
set -euo pipefail
: "${NAME:?}" "${ARM:?}" "${SEED:?}" "${HPC_CONFIG:?}"
EPOCHS="${EPOCHS:-200}"
WEIGHTS="${WEIGHTS:-yolov10m.yaml}"
IMGSZ="${IMGSZ:-960}"
# the optimizer is always fixed here (the recipe in docs/riders/preregistration.md, section 4)
OPT_ARGS="--optimizer AdamW --lr0 0.00125 --momentum 0.9 --warmup-bias-lr 0.0"

source "$HPC_CONFIG"
[ -f "$(dirname "$HPC_CONFIG")/config.local.env" ] && source "$(dirname "$HPC_CONFIG")/config.local.env"
for m in $MODULES; do module load "$m"; done
source "$HPC_ROOT/venv/bin/activate"
cd "$HPC_ROOT/repo"
export PYTHONPATH=.

SOURCE="$HPC_ROOT/data/rider_headroom"
[ -d "$SOURCE" ] || { echo "ERROR: $SOURCE is missing (upload the rider_headroom bundle first)" >&2; exit 1; }
[ -f "$SOURCE/arms/$ARM.txt" ] || { echo "ERROR: unknown arm $ARM (no $SOURCE/arms/$ARM.txt)" >&2; exit 1; }

# Copy the data to node-local scratch when the node offers it (thousands of small images are slow on shared storage).
LOCAL="${SLURM_TMPDIR:-${TMPDIR:-}}"
if [ -n "$LOCAL" ] && [ -d "$LOCAL" ]; then
  WORK="$LOCAL/vcv-rider-${SLURM_JOB_ID:-$$}"
  trap 'rm -rf "$WORK"' EXIT
  mkdir -p "$WORK"
  cp -r "$SOURCE" "$WORK/rider_headroom"
  DATA_ROOT="$WORK/rider_headroom"
else
  DATA_ROOT="$SOURCE"
fi

# The lists hold the Windows paths of the machine that built them: re-root them under DATA_ROOT and write data.yaml.
YAML_DIR="${WORK:-$HPC_ROOT/yaml}/rider_${ARM}"
mkdir -p "$YAML_DIR"
python - "$DATA_ROOT" "$ARM" "$YAML_DIR" <<'PY'
import sys
from pathlib import Path
from src.evaluation.class_maps import RIDER_PROFILE
from src.evaluation.portable import data_yaml, reroot_image_list

root, arm, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
lists = {}
for key, source in (("train", root / "arms" / f"{arm}.txt"), ("val", root / "val.txt")):
    lines = reroot_image_list(source.read_text(encoding="utf-8").splitlines(), root)
    target = out / f"{key}.txt"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    lists[key] = target
names = {i: RIDER_PROFILE.classes[c] for i, c in enumerate(RIDER_PROFILE.class_order)}
(out / "data.yaml").write_text(data_yaml([lists["train"]], lists["val"], names), encoding="utf-8")
print("data:", out / "data.yaml", "train images:", len(lists["train"].read_text().split()))
PY
YAML="$YAML_DIR/data.yaml"

echo "=== $NAME: training (arm $ARM, seed $SEED, $EPOCHS epochs) ==="
python bin/train_detector.py --data "$YAML" --weights "$WEIGHTS" --name "$NAME" \
  --project "$HPC_ROOT/runs" --epochs "$EPOCHS" --imgsz "$IMGSZ" --batch "${BATCH:-8}" --seed "$SEED" \
  --workers 4 --mosaic 1.0 --close-mosaic 10 $OPT_ARGS

echo "=== $NAME: BDD100K (rider profile) ==="
python bin/evaluate_detector.py --weights "$HPC_ROOT/runs/$NAME/weights/best.pt" \
  --class-space ours --profile riders --benchmark bdd100k \
  --labels "$HPC_ROOT/data/bdd100k/labels/100k/val" --images "$HPC_ROOT/data/bdd100k/images/100k/val" \
  --imgsz "$IMGSZ" --conf 0.001 --iou 0.6 --max-det 100 --device 0 \
  --out "$HPC_ROOT/results/${NAME}_bdd100k_riders.json"

echo "=== $NAME: Cityscapes (rider profile) ==="
python bin/evaluate_detector.py --weights "$HPC_ROOT/runs/$NAME/weights/best.pt" \
  --class-space ours --profile riders --benchmark cityscapes --cityscapes-root "$HPC_ROOT/data/cityscapes" \
  --imgsz "$IMGSZ" --conf 0.001 --iou 0.6 --max-det 100 --device 0 \
  --out "$HPC_ROOT/results/${NAME}_cityscapes_riders.json"

echo "=== $NAME: ALL DONE ==="
