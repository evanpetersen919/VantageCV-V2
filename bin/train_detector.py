"""Train a YOLOv10 detector on the exported synthetic dataset (needs PyTorch + ultralytics).

Run this from a separate training environment (see ``docs`` note below), not the project's
main one: PyTorch and ultralytics are deliberately not project dependencies.

The two arms that matter for a fair sim-to-real claim differ only in ``--weights``:

* ``--weights yolov10m.yaml``  -- random initialisation: nothing seen a real image, so the
  result measures what the synthetic data alone teaches;
* ``--weights F:/yolov10m.pt`` -- COCO-pretrained (real images already in the weights):
  measures what synthetic fine-tuning adds on top, and must not be read as synthetic-only.

    PYTHONPATH=. python bin/train_detector.py --data live_dataset/train2000/data.yaml \\
        --weights yolov10m.yaml --name synthetic_scratch --epochs 100 --imgsz 1280 --batch 8

Training environment: ``python -m venv .venv-train`` then, inside it, install a CUDA build of
PyTorch from pytorch.org followed by ``pip install ultralytics pycocotools``.

``--mosaic`` defaults to ultralytics' own default (1.0). The v5a ablation
(``EXPERIMENT_LOG.md``) found ``--mosaic 0`` a real, consistent, if modest, win on real-image
transfer for this project's single-coherent-scene images -- pass it explicitly to use that.
``--close-mosaic`` defaults to ultralytics' own 10. With ``--mosaic 0`` it changes nothing about
the augmentation (mosaic is already off), but ``--close-mosaic 0`` skips the end-of-run dataloader
rebuild, which deadlocked once on Windows (see ``EXPERIMENT_LOG.md``).
"""

import argparse
from pathlib import Path


def main() -> None:
    """Parse arguments and run ultralytics training."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--weights", required=True, help="yolov10m.yaml (scratch) or a .pt file")
    parser.add_argument("--name", required=True)
    parser.add_argument("--project", type=Path, default=Path("runs"))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--mosaic", type=float, default=1.0)
    parser.add_argument("--close-mosaic", type=int, default=10)
    parser.add_argument(
        "--optimizer",
        default="auto",
        help="'auto' lets ultralytics pick (MuSGD for long runs, AdamW for short ones, so arms "
        "of different size can differ); name one (e.g. AdamW) with --lr0/--momentum to fix it",
    )
    parser.add_argument("--lr0", type=float, default=None, help="initial learning rate")
    parser.add_argument("--momentum", type=float, default=None)
    parser.add_argument(
        "--warmup-bias-lr",
        type=float,
        default=None,
        help="'auto' sets this to 0.0 when it picks AdamW; pass 0.0 to match that",
    )
    args = parser.parse_args()
    optimizer_args = {"optimizer": args.optimizer}
    if args.lr0 is not None:
        optimizer_args["lr0"] = args.lr0
    if args.momentum is not None:
        optimizer_args["momentum"] = args.momentum
    if args.warmup_bias_lr is not None:
        optimizer_args["warmup_bias_lr"] = args.warmup_bias_lr

    # Without exist_ok, ultralytics saves into ``<name>-2`` when ``<name>`` exists (a retry after a
    # failed job then trains into a folder the scoring step does not look in). So a run always
    # writes to ``<project>/<name>``; one that already holds weights is refused, not overwritten.
    finished = args.project.resolve() / args.name / "weights" / "best.pt"
    if finished.exists():
        parser.error(f"{finished} exists: pick another --name or remove the finished run")

    from ultralytics import YOLO  # pylint: disable=import-outside-toplevel,import-error

    model = YOLO(args.weights)
    model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        seed=args.seed,
        device=args.device,
        workers=args.workers,
        project=str(args.project.resolve()),
        name=args.name,
        exist_ok=True,
        mosaic=args.mosaic,
        close_mosaic=args.close_mosaic,
        deterministic=True,
        **optimizer_args,
    )


if __name__ == "__main__":
    main()
