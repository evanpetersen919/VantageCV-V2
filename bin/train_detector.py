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
    args = parser.parse_args()

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
        deterministic=True,
    )


if __name__ == "__main__":
    main()
