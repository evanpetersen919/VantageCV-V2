# Training on a cluster

Training and evaluation move to the cluster; image generation stays local (it needs UE5).
Run every comparison on **one** machine: results from different GPUs or library versions are not
comparable, even with the same seed. The planned jobs below therefore re-run both arms (real-only
and real + synthetic, three seeds each) on the cluster.

## 1. Cluster facts (run on the cluster, then put your values in `hpc/config.local.env`)

```bash
sinfo -o "%P %G %l %c"        # partitions, GPUs, time limits, CPUs
nvidia-smi                    # GPU model and driver (pick a matching TORCH_INDEX)
module avail python cuda      # modules to put in MODULES, if your site uses them
```

## 2. Package the data (on your PC, Git Bash)

About 8.6 GB. Check it afterwards with `tar -tf vantagecv_data.tar | head`.

```bash
tar -cf vantagecv_data.tar \
  -C /f/vscode/VantageCV-V2/live_dataset \
    train2000_v5/images train2000_v5/labels train2000_v5/train.txt train2000_v5/val.txt \
  -C /f/datasets \
    bdd100k_control bdd100k/images/100k/val bdd100k/labels/100k/val \
    cityscapes/leftImg8bit/val cityscapes/gtFine/val
scp vantagecv_data.tar <you>@<cluster>:~/vantagecv/
```

## 3. One-time setup (on the cluster)

```bash
git clone https://github.com/evanpetersen919/VantageCV-V2.git ~/vantagecv/repo
cd ~/vantagecv/repo
cp hpc/config.env hpc/config.local.env   # your copy; git-ignored, so pulls never conflict
nano hpc/config.local.env                # fill in HPC_ROOT, partition, time limit, modules
bash hpc/setup_env.sh                     # venv + pinned libraries; prints the versions
mkdir -p ~/vantagecv/data && tar -xf ~/vantagecv/vantagecv_data.tar -C ~/vantagecv/data
source ~/vantagecv/venv/bin/activate
PYTHONPATH=. python bin/hpc_make_data.py --root ~/vantagecv/data --out ~/vantagecv/yaml
```

Compare the printed versions with the local runs (torch 2.14.0+cu126, ultralytics 8.4.163).

## 4. Smoke test, then the real jobs

```bash
bash hpc/submit.sh smoke real_control 0 1.0 10 2     # 2 epochs: checks data, GPU and both evaluations
squeue -u $USER                                       # then read ~/vantagecv/logs/smoke_*.log
bash hpc/submit_planned.sh                            # 6 jobs: real-only and mixed, seeds 0-2
```

## 5. Bring results back

```bash
scp "<you>@<cluster>:~/vantagecv/results/*.json" F:/vscode/VantageCV-V2/results/
```

Then log them in `EXPERIMENT_LOG.md`. Weights stay on the cluster under `~/vantagecv/runs/`.

## Notes

- Raise `SLURM_TIME` in `config.local.env` if the GPU is slower than an RTX 4080 (the mixed run is about
  5 h on that card).
- Once in a while ultralytics deadlocks rebuilding its dataloader near the end of a run (seen once
  locally, at epoch 191). If a job stops logging for ~30 minutes, `scancel` it and resume from its
  last checkpoint, which finishes the same 200-epoch recipe (do **not** resubmit with
  `--close-mosaic 0` for the mosaic-on runs: that keeps mosaic on for the last 10 epochs, a
  different recipe):

  ```bash
  source $HPC_ROOT/venv/bin/activate && cd $HPC_ROOT/repo
  python -c "from ultralytics import YOLO; YOLO('$HPC_ROOT/runs/NAME/weights/last.pt').train(resume=True)"
  ```

  Then run the two evaluations from `hpc/run_arm.sbatch` by hand on the resumed `best.pt`.
