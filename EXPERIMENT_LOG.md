# Experiment Log — Sim-to-Real Detection Transfer

Tracks every synthetic-data training run for the train-synthetic/test-real experiment: what
changed, why, and what happened on the real benchmarks (BDD100K val, 10,000 images; Cityscapes
val, 500 images). Each entry is written after the run's evaluation completes, not before —
numbers here are always measured, never predicted.

All arms use YOLOv10m, imgsz 960, eval settings `--conf 0.001 --iou 0.6 --max-det 100`.
"Scratch" = trained from `yolov10m.yaml` for 200 epochs. "Fine-tune" = trained from COCO
weights (`yolov10m.pt`) for 50 epochs. Real-control = 1,838 real BDD100K training images,
equal size to the synthetic training set, trained the same way as scratch — the fair
same-data-volume reference point.

The entries are in order of when they were run, one file each under [`docs/experiments/`](docs/experiments/); each is written after its evaluation completes.

| # | Entry |
|---|---|
| 1 | [Reference arms (not synthetic, for scale)](docs/experiments/01_reference-arms-not-synthetic-for-scale.md) |
| 2 | [v1 — first live-rendered dataset (2,037 images, 800 scenarios)](docs/experiments/02_v1-first-live-rendered-dataset-2-037-images-800-scenarios.md) |
| 3 | [v2 — occlusion label fix only](docs/experiments/03_v2-occlusion-label-fix-only.md) |
| 4 | [v3 — distance cutoff + night lighting variety + vehicle color diversity (fresh 2,037-image render)](docs/experiments/04_v3-distance-cutoff-night-lighting-variety-vehicle-color-dive.md) |
| 5 | [v4a — image realism post-process (blur + desaturate + JPEG round-trip)](docs/experiments/05_v4a-image-realism-post-process-blur-desaturate-jpeg-round-tr.md) |
| 6 | [v4b — modal occlusion boxes](docs/experiments/06_v4b-modal-occlusion-boxes.md) |
| 7 | [v5a — mosaic ablation (quick signal)](docs/experiments/07_v5a-mosaic-ablation-quick-signal.md) |
| 8 | [v5b — camera/material/asset changes ready for the v5 render (implemented, not yet rendered)](docs/experiments/08_v5b-camera-material-asset-changes-ready-for-the-v5-render-im.md) |
| 9 | [Priority list: most critical to least critical (post-v4b/v5a synthesis)](docs/experiments/09_priority-list-most-critical-to-least-critical-post-v4b-v5a-s.md) |
| 10 | [v5 — camera pitch + material/species variety + trailer fix (real re-render)](docs/experiments/10_v5-camera-pitch-material-species-variety-trailer-fix-real-re.md) |
| 11 | [Grad-CAM v3 — rebuilt tool, first v5 baseline (priority-list #1, Step 0)](docs/experiments/11_grad-cam-v3-rebuilt-tool-first-v5-baseline-priority-list-1-s.md) |
| 12 | [Segmentation-guided background stylization (priority-list #1, Step 1) — negative result, real diagnosis](docs/experiments/12_segmentation-guided-background-stylization-priority-list-1-s.md) |
| 13 | [Segmentation-guided background stylization, calibrated retry — real, positive Grad-CAM shift, AP roughly flat](docs/experiments/13_segmentation-guided-background-stylization-calibrated-retry.md) |
| 14 | [v6 — always-on material appearance jitter (priority-list #1, Step 2) — no measurable gain](docs/experiments/14_v6-always-on-material-appearance-jitter-priority-list-1-step.md) |
| 15 | [v6 + calibrated background stylization (stacking test) — no gain, Grad-CAM mixed](docs/experiments/15_v6-calibrated-background-stylization-stacking-test-no-gain-g.md) |
| 16 | [Seed repeats — run-to-run noise is large (priority-list #4)](docs/experiments/16_seed-repeats-run-to-run-noise-is-large-priority-list-4.md) |
| 17 | [Real + synthetic (mixed training) — first positive value signal, modest](docs/experiments/17_real-synthetic-mixed-training-first-positive-value-signal-mo.md) |
| 18 | [Real vs real + synthetic, three seeds each, on the cluster — first statistically supported gain, small and class-specific](docs/experiments/18_real-vs-real-synthetic-three-seeds-each-on-the-cluster-first.md) |
| 19 | [Data-volume control and data-efficiency sweep (cluster, 3 seeds each)](docs/experiments/19_data-volume-control-and-data-efficiency-sweep-cluster-3-seed.md) |
| 20 | [Synthetic pre-training then real fine-tuning, vs mixed training (cluster, 3 seeds each)](docs/experiments/20_synthetic-pre-training-then-real-fine-tuning-vs-mixed-traini.md) |
| 21 | [Synthetic volume test: a second batch, 3,691 synthetic images (cluster, 3 seeds each)](docs/experiments/21_synthetic-volume-test-a-second-batch-3-691-synthetic-images.md) |
| 22 | [Correction: the optimizer differs between arms (found in review, verified)](docs/experiments/22_correction-the-optimizer-differs-between-arms-found-in-revie.md) |
| 23 | [Optimizer-controlled re-runs, step-matched control, truck/bus ablation (cluster)](docs/experiments/23_optimizer-controlled-re-runs-step-matched-control-truck-bus.md) |
| 24 | [Generator audit and the v7 realism profile (measured, not yet trained)](docs/experiments/24_generator-audit-and-the-v7-realism-profile-measured-not-yet.md) |
| 25 | [v7 first batch and the visible-part label set: what was built, before any training result](docs/experiments/25_v7-first-batch-and-the-visible-part-label-set-what-was-built.md) |
| 26 | [Pixel realism in the mixed regime, and the AdamW mixed arm completed (cluster, 3 seeds)](docs/experiments/26_pixel-realism-in-the-mixed-regime-and-the-adamw-mixed-arm-co.md) |
| 27 | [Visible-part labels and the first v7 batch (cluster, 3 seeds each, AdamW)](docs/experiments/27_visible-part-labels-and-the-first-v7-batch-cluster-3-seeds-e.md) |
| 28 | [Road gloss in clear weather: measured, and a dry road for v7](docs/experiments/28_road-gloss-in-clear-weather-measured-and-a-dry-road-for-v7.md) |
| 29 | [Tractor-trailer rigs (the City Sample semi), built and checked by rendering](docs/experiments/29_tractor-trailer-rigs-the-city-sample-semi-built-and-checked.md) |
| 30 | [Lane markings: double yellow centre lines, white lane lines and stop lines (2026-10-09)](docs/experiments/30_lane-markings-painted-centre-lines-lane-lines-and-stop-lines.md) |
| 31 | [Signal poles show their intersection's phase (2026-10-09)](docs/experiments/31_signal-poles-show-their-intersection-s-phase.md) |
| 32 | [Leafy street trees: vegetation share from 0 to 15% (2026-10-09)](docs/experiments/32_leafy-street-trees-vegetation-share-from-0-to-15-percent.md) |
| 33 | [Tree quality and curb planting: grass, shrubs, hedges (2026-10-09)](docs/experiments/33_tree-quality-and-curb-planting-grass-shrubs-hedges.md) |
| 34 | [Scanned, photographic street trees and shrubs (2026-10-10)](docs/experiments/34_scanned-photographic-street-trees.md) |
| 35 | [Rider headroom check: more real rider images help a lot (2026-10-10)](docs/experiments/35_rider-headroom-check-result.md) |
