# Experiment submit scripts

One script per study, kept as the record of exactly which jobs produced which entry in
`EXPERIMENT_LOG.md` (arm names, seeds, scene sets). They are not general tools: for a new study,
copy the closest one and change the arm names. The general tools stay one level up
(`hpc/submit.sh`, `submit_eval.sh`, `submit_scene_eval.sh`, `submit_box_outcomes.sh`,
`submit_sweep.sh`). Run from the repository root, e.g. `bash hpc/experiments/submit_v13.sh`.
