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

## 7. Synthetic-volume test (fourth batch)

Does a second synthetic batch (`train2000_v5b`: same generator, new seeds, 1,853 train images) add
anything? Real data + both batches (3,691 synthetic) is compared with real + the first batch only.

On your PC, send the second batch (about 6.3 GB):

```bash
scp /f/hpc_upload/vantagecv_synth_b.tar <you>@<cluster>:~/vantagecv/
```

On the cluster:

```bash
cd ~/vantagecv/repo && git pull
tar -xf ~/vantagecv/vantagecv_synth_b.tar -C ~/vantagecv/data
source ~/vantagecv/venv/bin/activate
PYTHONPATH=. python bin/hpc_make_data.py --root ~/vantagecv/data --out ~/vantagecv/yaml
PYTHONPATH=. python bin/hpc_check_data.py --yaml-dir ~/vantagecv/yaml
bash hpc/submit_scale.sh          # 6 jobs: hpc_mixed25big_s*, hpc_mixedbig_s*
```

The check must list `mixed_25pct_big` (train 4151), `mixed_50pct_big` (4610) and `mixed_big` (5529),
all `OK`. Compare with `bin/analyze_runs.py --baseline hpc_real25 --arms hpc_mixed25 hpc_mixed25big`
(and `hpc_real_only` with `hpc_mixed hpc_mixedbig`).

## 8. Optimizer control (fifth batch)

Ultralytics' default `optimizer=auto` picks MuSGD for long runs (`ceil(N/64) x epochs > 10,000`,
which is every arm with more than about 3,200 images) and AdamW for short ones, so arms of different
size trained with different optimizers. This batch re-runs the affected arms with AdamW fixed
(`OPTIMIZER=AdamW` makes `run_arm.sbatch` pass `--optimizer AdamW --lr0 0.00125 --momentum 0.9
--warmup-bias-lr 0.0`, the same values `auto` uses for AdamW), plus a real-only run with the same
number of optimizer steps as the 3,676-image arms (400 epochs):

```bash
cd ~/vantagecv/repo && git pull
bash hpc/submit_optimizer_control.sh      # 15 jobs, names hpc_adamw_*
```

A job started correctly if its log shows `optimizer: AdamW(lr=0.00125, momentum=0.9)` (grep for
`optimizer:`); a line saying `MuSGD` means the setting was not applied. The longest jobs
(`hpc_adamw_mixedbig`, `hpc_adamw_real400`) need the raised `SLURM_TIME` you used for the big runs.
Compare with `bin/analyze_runs.py --baseline hpc_adamw_real400 --arms hpc_adamw_mixed` (and
`hpc_adamw_real3676`, `hpc_adamw_mixedbig`).

## 9. Do synthetic trucks and buses carry the gain? (sixth batch)

Only 510 of the 3,691 synthetic training images contain neither a truck nor a bus. At 25% real
(460 images), `hpc_notb25_*` adds exactly those 510; `hpc_rand25_*` adds 510 randomly chosen
synthetic images instead (same count, same real images). Both use AdamW. If the no-truck/bus set
keeps the gain, including on truck and bus AP, the synthetic trucks and buses are not what helps.
No new data is needed (the lists are built from `train2000_v5` and `train2000_v5b`):

```bash
cd ~/vantagecv/repo && git pull
source ~/vantagecv/venv/bin/activate
PYTHONPATH=. python bin/hpc_make_data.py --root ~/vantagecv/data --out ~/vantagecv/yaml
PYTHONPATH=. python bin/hpc_check_data.py --yaml-dir ~/vantagecv/yaml   # mixed_25pct_notb and _rand: train 970
bash hpc/submit_truckbus_test.sh      # 6 jobs: hpc_notb25_s*, hpc_rand25_s*
```

Compare with `bin/analyze_runs.py --baseline hpc_rand25 --arms hpc_notb25` (and `hpc_real25` for the
no-synthetic reference).

## 10. Visible-part (modal) label test

The same v5 images with regenerated labels: a partly hidden car, truck, bus or pedestrian is boxed
only where it can be seen, as BDD100K boxes it (half of v5's boxes shrink, median remaining area
56%; class counts barely change). Compared with the original labels on the same images, 25% and
100% real, AdamW, 3 seeds. Only labels travel (a few MB); the images are hard-linked from
`train2000_v5` on the cluster:

```bash
# PC (PowerShell)
scp F:\hpc_upload\vantagecv_v5_modal_labels.tar peter337@hpc-login:/scratch/peter337/VantageCV/

# cluster
cd /scratch/peter337/VantageCV/data
tar -xf ../vantagecv_v5_modal_labels.tar                 # train2000_v5_modal/{labels,train.txt,val.txt}
cp -al train2000_v5/images train2000_v5_modal/images      # hard links: no extra space
cd ../repo && git pull
source ../venv/bin/activate && export YOLO_CONFIG_DIR=/scratch/peter337/yolo_config
PYTHONPATH=. python bin/hpc_make_data.py --root ../data --out ../yaml
PYTHONPATH=. python bin/hpc_check_data.py --yaml-dir ../yaml   # mixed_modal 3676, mixed_25pct_modal 2298
bash hpc/submit_modal_test.sh                             # 6 jobs: hpc_modal25_s*, hpc_adamw_modal_s*
```

Compare `hpc_modal25` with `hpc_mixed25` and `hpc_adamw_modal` with `hpc_adamw_mixed`.

## 11. First v7 batch

512 images from the v7 generator (visible-part labels, v7 fleet with pickups counted as cars,
calibrated night, hood on half the frames, per-scenario pedestrian density, ego views only;
seeds 70000-70255), 25% real, AdamW, 3 seeds. Compare `hpc_v7a25` with `hpc_rand25`: the same
number of training images (972 vs 970) from the earlier generator.

```bash
# PC (PowerShell): about 1.5 GB
scp F:\hpc_upload\vantagecv_v7a.tar peter337@hpc-login:/scratch/peter337/VantageCV/

# cluster
cd /scratch/peter337/VantageCV/data && tar -xf ../vantagecv_v7a.tar          # train_v7a/
cd ../repo && git pull
source ../venv/bin/activate && export YOLO_CONFIG_DIR=/scratch/peter337/yolo_config
PYTHONPATH=. python bin/hpc_make_data.py --root ../data --out ../yaml
PYTHONPATH=. python bin/hpc_check_data.py --yaml-dir ../yaml    # mixed_25pct_v7a: train 972
bash hpc/submit_v7a.sh                                           # 3 jobs: hpc_v7a25_s*
```

## 12. Does the supply of scarce-class instances decide a supplement's value?

The first v7 batch matched real class frequencies and scored below an equal-size random draw from
the older generator, with each class moving in step with how many of its instances were supplied
(person 0.40x instances, -0.89 AP; truck 0.19x, -1.18; car 1.10x, +0.46). This tests it directly,
without rendering: 510 of the existing v5/v5b images, 25% real, AdamW, 3 seeds each.

| Arm | Selection | Persons / cars / buses / trucks supplied |
|---|---|---|
| `hpc_poor25` | fewest persons and trucks | 547 / 3,671 / 89 / 226 (the v7 batch: 508 / 4,201 / 57 / 209) |
| `hpc_rand25` (already run) | random | 1,256 / 3,821 / 69 / 1,120 |
| `hpc_rich25` | most persons, trucks and buses | 2,052 / 3,691 / 245 / 1,800 |

Needs only `git pull` (v5 and v5b are already on the cluster):

```bash
cd /scratch/peter337/VantageCV/repo && git pull
source ../venv/bin/activate && export YOLO_CONFIG_DIR=/scratch/peter337/yolo_config
PYTHONPATH=. python bin/hpc_make_data.py --root ../data --out ../yaml
PYTHONPATH=. python bin/hpc_check_data.py --yaml-dir ../yaml   # mixed_25pct_poor / _rich: train 970
bash hpc/submit_supply_test.sh                                  # 6 jobs
```

Read: if `hpc_poor25` scores like `hpc_v7a25` (and below `hpc_rand25`), supply alone explains the v7
deficit; if `hpc_rich25` beats `hpc_rand25`, oversampling the scarce classes is a free gain.

## 13. Recovering runs that trained but were not scored

If a job fails after training (for example the environment was damaged), its weights are still in
`$HPC_ROOT/runs/<name>/weights/best.pt`. Repair the cause, then score without retraining:

```bash
bash hpc/submit_eval.sh NAME1 NAME2 ...   # or no names: every run under runs/ that lacks results
```

Each `eval_<name>` job runs only the two evaluations from `hpc/run_arm.sbatch` and writes the same
`<name>_bdd100k.json` / `<name>_cityscapes.json` files.

## 14. Bring results back

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

## 15. Per-scene scores of trained arms

Does a model fail on scene types the generator never shows (highway, residential)? BDD100K labels each
image's scene; this scores trained arms again with it added to the time-of-day and weather breakdown
(no retraining, BDD100K only, about an hour per job). Arms are given without the seed; each seed whose
weights exist gets one job:

```bash
cd /scratch/peter337/VantageCV/repo && git pull
bash hpc/submit_scene_eval.sh hpc_real25 hpc_rand25 hpc_v7p25     # up to 9 jobs
```

Copy back `hpc_*_bdd100k_scene.json` and compare scenes with
`python bin/analyze_runs.py --baseline hpc_real25 --arms hpc_rand25 hpc_v7p25` (the benchmark is
`bdd100k_scene`). Reading rule, set before the results: if highway or residential trail city street by
more than about 2 AP in the synthetic arms but not in the real-only arm, build that scene type next;
otherwise scene coverage is not where the models fail.

## 16. How are truck and bus boxes missed? (per-box outcomes)

AP says a class trails; this says why. For every real BDD100K val box, a trained arm either finds it
(right class), calls it something else (car, bus...), finds it only at low confidence, or misses it, by
box size and time of day. No retraining; about 10-15 minutes per seed:

```bash
cd /scratch/peter337/VantageCV/repo && git pull
bash hpc/submit_box_outcomes.sh hpc_real25r hpc_rand25 hpc_v7p25 hpc_v8a25      # up to 12 jobs
scp ... hpc_*_box_outcomes.json            # copy back, then summarise on the PC
```

Reading rule, fixed first: if most missed truck boxes are *mislabelled* (wrong_class) the cause is
appearance confusion with cars or buses; if they are *missed or low-confidence*, the detector does not
find them at all and the cause is visibility or scale; compare the synthetic arms with the real-only
arm, and read the size bins before the totals.
