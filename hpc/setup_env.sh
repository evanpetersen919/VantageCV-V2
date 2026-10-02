#!/bin/bash
# One-time cluster setup: clone the repo, create the training venv, record versions.
# Run on a login node (it needs internet): bash hpc/setup_env.sh   (after editing hpc/config.env)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
[ -f "$HERE/config.local.env" ] && source "$HERE/config.local.env"
for m in $MODULES; do module load "$m"; done

mkdir -p "$HPC_ROOT"/{data,yaml,runs,results,logs}
if [ ! -d "$HPC_ROOT/repo/.git" ]; then
  git clone https://github.com/evanpetersen919/VantageCV-V2.git "$HPC_ROOT/repo"
fi

python3 -m venv "$HPC_ROOT/venv"
source "$HPC_ROOT/venv/bin/activate"
pip install --upgrade pip
# Pinned torch first; if the exact build is not on the index, fall back to the newest and warn.
pip install "torch==2.14.0" "torchvision==0.29.0" --index-url "$TORCH_INDEX" \
  || { echo "WARNING: pinned torch not available; installing newest -- results may not match local runs"; \
       pip install torch torchvision --index-url "$TORCH_INDEX"; }
pip install -r "$HERE/requirements-train.txt"

python - <<'PY' | tee "$HPC_ROOT/logs/env_versions.txt"
import sys, torch, ultralytics
print("python", sys.version.split()[0])
print("torch", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available())
print("ultralytics", ultralytics.__version__)
PY
echo "Done. Versions saved to $HPC_ROOT/logs/env_versions.txt (compare with the local run: torch 2.14.0+cu126, ultralytics 8.4.163)."
