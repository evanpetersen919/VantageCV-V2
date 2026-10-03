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

## 5. Control and data-efficiency runs (second batch)

Answers two questions the first batch left open: is the gain just from having 2x the data (control:
3,676 real images), and how does it change with less real data (25% / 50% of the 1,838).
All of these validate on the same 199 real images, same recipe, seeds 0-2.

On your PC, pack the extra 1,838 disjoint real images (about 137 MB) and send them:

```bash
tar -cf /f/hpc_upload/vantagecv_extra.tar -C /f/datasets bdd100k_control_extra
scp /f/hpc_upload/vantagecv_extra.tar <you>@<cluster>:~/vantagecv/
```

On the cluster:

```bash
cd ~/vantagecv/repo && git pull                       # config.local.env is git-ignored, so it is kept
tar -xf ~/vantagecv/vantagecv_extra.tar -C ~/vantagecv/data
source ~/vantagecv/venv/bin/activate
PYTHONPATH=. python bin/hpc_make_data.py --root ~/vantagecv/data --out ~/vantagecv/yaml
PYTHONPATH=. python bin/hpc_check_data.py --yaml-dir ~/vantagecv/yaml
```

The check must end with every line `OK` and these counts (train / val):

| data file | train | val |
|---|---|---|
| real_control | 1838 | 199 |
| mixed_real_v5 | 3676 | 199 |
| real_3676 | 3676 | 199 |
| real_25pct / mixed_25pct | 460 / 2298 | 199 |
| real_50pct / mixed_50pct | 919 / 2757 | 199 |

Then submit:

```bash
bash hpc/submit_control.sh          # 3 jobs: hpc_real3676_s0-2
bash hpc/submit_sweep.sh 25         # 6 jobs: hpc_real25_s*, hpc_mixed25_s*
bash hpc/submit_sweep.sh 50         # 6 jobs: hpc_real50_s*, hpc_mixed50_s*
```

Check that a job started correctly (about 2-3 minutes after it leaves `PENDING`):

```bash
squeue -u $USER                                  # state R (running); PD means waiting for a GPU
tail -n 40 ~/vantagecv/logs/hpc_real3676_s0_*.log
grep -E "train: Scanning|val: Scanning" ~/vantagecv/logs/hpc_real3676_s0_*.log | head
```

In the log, `train: Scanning ... 3676 images` (the counts in the table above), a `val` scan of 199, no
`Traceback`, then epoch lines `1/200` with a changing loss. Finished jobs print `ALL DONE` and leave
`~/vantagecv/results/<name>_bdd100k.json` and `_cityscapes.json`; `sacct -j <id> --format=State,Elapsed`
shows `COMPLETED`. The two batches can run together if the GPUs are free; they are independent.

## 6. Synthetic pre-training, then real fine-tuning (third batch)

Tests the alternative to mixed training: learn from the synthetic images first, then fine-tune on
the real ones. Needs no new data, only `git pull`:

```bash
cd ~/vantagecv/repo && git pull
bash hpc/submit_pretrain.sh        # 12 jobs
```

Three synthetic-only runs (`hpc_pretrain_s0-2`, 200 epochs, no mosaic) start at once. Each has
three fine-tunes (`hpc_ft25_s*`, `hpc_ft50_s*`, `hpc_ft100_s*`: 50 epochs on 25% / 50% / 100% of the
real images) that wait for their own pre-train (`squeue` shows them as `PD` with reason
`Dependency`; they start on their own once it finishes). If a pre-train fails, its fine-tunes are
cancelled by Slurm rather than run from missing weights. Fine-tune seed k starts from pre-train
seed k. Compare with `bin/analyze_runs.py --baseline hpc_mixed25 --arms hpc_ft25` (and 50, `hpc_mixed`).

## 7. Bring results back

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
