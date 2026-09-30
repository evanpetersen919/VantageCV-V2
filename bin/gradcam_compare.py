"""Grad-CAM overlays for a YOLOv10m checkpoint, on a fixed real-image panel.

The original Grad-CAM script that produced ``runs/gradcam/`` and ``runs/gradcam_v2/`` was run
ad hoc and never committed -- it no longer exists anywhere in this repo or its git history.
This rewrites it as a real, committed tool, reusing the same real-image panel (the exact same
11 images: 5 BDD100K day, 3 BDD100K night, 3 Cityscapes) so a new checkpoint's overlays are
directly, visually comparable to the surviving ``runs/gradcam_v2/`` PNGs.

Hooks the same three detection-scale feature maps as before (confirmed against the model's own
graph, not assumed): ``model.model.model[16]``/``[19]``/``[22]`` -- the P3/P4/P5 inputs to
YOLOv10's detect head (stride 8/16/32). Uses ``pytorch_grad_cam`` (already an installed
``.venv-train`` dependency) for the actual CAM math -- ``ReLU(mean-pooled-gradient x
activation)``, the standard Grad-CAM formula -- rather than reimplementing it by hand.

YOLOv10's raw forward pass returns ``(prediction_tensor, aux_dict)``, not a plain tensor, so a
thin wrapper strips the tensor out before handing the model to ``pytorch_grad_cam`` (its batch
loop assumes the model returns something it can iterate per-image). The Grad-CAM "target" is
the single highest class-confidence cell anywhere in the prediction (any class, any anchor) --
this project's own stated Grad-CAM discipline ("the model's own top prediction"), not a
fixed target class.

    .venv-train/Scripts/python.exe bin/gradcam_compare.py \\
        --weights runs/synth_scratch_v5/weights/best.pt --tag v5_scratch --out runs/gradcam_v3
"""

import argparse
from pathlib import Path
from typing import Any, List, Tuple

import numpy as np
import numpy.typing as npt
from PIL import Image

IMGSZ = 960

# The exact 11 real images runs/gradcam_v2/ was built from (5 BDD100K day, 3 BDD100K night,
# 3 Cityscapes) -- reused verbatim so a new checkpoint's overlays are directly comparable.
BDD_ROOT = Path("F:/datasets/bdd100k/images/100k/val")
CITYSCAPES_ROOT = Path("F:/datasets/cityscapes/leftImg8bit/val/frankfurt")
PANEL: Tuple[Tuple[str, Path], ...] = (
    ("bdd_day_b72f72e4-02ac60a7", BDD_ROOT / "b72f72e4-02ac60a7.jpg"),
    ("bdd_day_c1252e1f-a88318f0", BDD_ROOT / "c1252e1f-a88318f0.jpg"),
    ("bdd_day_c457d18a-610011a8", BDD_ROOT / "c457d18a-610011a8.jpg"),
    ("bdd_day_c599480d-15223a32", BDD_ROOT / "c599480d-15223a32.jpg"),
    ("bdd_day_c663ebc6-46365c70", BDD_ROOT / "c663ebc6-46365c70.jpg"),
    ("bdd_night_b3158519-6afea489", BDD_ROOT / "b3158519-6afea489.jpg"),
    ("bdd_night_c39375fb-4de2d085", BDD_ROOT / "c39375fb-4de2d085.jpg"),
    ("bdd_night_c5125543-1bb695f3", BDD_ROOT / "c5125543-1bb695f3.jpg"),
    (
        "cityscapes_frankfurt_000001_003588_leftImg8bit",
        CITYSCAPES_ROOT / "frankfurt_000001_003588_leftImg8bit.png",
    ),
    (
        "cityscapes_frankfurt_000001_041664_leftImg8bit",
        CITYSCAPES_ROOT / "frankfurt_000001_041664_leftImg8bit.png",
    ),
    (
        "cityscapes_frankfurt_000001_055603_leftImg8bit",
        CITYSCAPES_ROOT / "frankfurt_000001_055603_leftImg8bit.png",
    ),
)


def _load_letterboxed(
    path: Path, imgsz: int
) -> Tuple[npt.NDArray[np.uint8], npt.NDArray[np.float32], Tuple[int, int]]:
    """A real image, letterboxed to ``imgsz`` x ``imgsz`` (matching ultralytics' own
    preprocessing), as both a normalized input array and a float [0,1] RGB array for overlay.
    Also returns the resized (pre-padding) content's (height, width), so the padding strip can
    be cropped back out of the final overlay -- most of this project's real images are wider
    than square, so a full 960x960 canvas is otherwise half blank grey padding."""
    import cv2  # pylint: disable=import-outside-toplevel,import-error

    image = np.array(Image.open(path).convert("RGB"))
    height, width = image.shape[:2]
    scale = min(imgsz / height, imgsz / width)
    resized = cv2.resize(image, (int(width * scale), int(height * scale)))
    canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    canvas[: resized.shape[0], : resized.shape[1]] = resized
    return canvas, canvas.astype(np.float32) / 255.0, resized.shape[:2]


def _grad_cam_helpers(torch_module: Any) -> Tuple[Any, Any]:
    """The two small torch-dependent helper classes, built once torch is known importable --
    kept out of module scope so the heavy ``torch``/``pytorch_grad_cam`` imports stay deferred
    (this project's convention for the main venv, which doesn't have these installed)."""

    class _RawOutputOnly(torch_module.nn.Module):  # type: ignore[misc]
        # pylint: disable=too-few-public-methods
        """YOLOv10's raw forward returns (prediction_tensor, aux_dict); pytorch_grad_cam's
        batch loop needs a plain per-image-iterable tensor, so this strips the aux dict."""

        def __init__(self, yolo_net: Any) -> None:
            super().__init__()
            self.yolo_net = yolo_net

        def forward(self, x: Any) -> Any:
            """The wrapped net's raw prediction tensor, dropping its aux dict."""
            output = self.yolo_net(x)
            return output[0] if isinstance(output, tuple) else output

    class _TopPredictionTarget:  # pylint: disable=too-few-public-methods
        """The model's own single highest class-confidence cell, any class, any anchor --
        channels 0-3 of YOLOv10's [8, num_anchors] output are box coordinates, 4-7 are
        per-class scores (this project has 4 classes: person/car/bus/truck)."""

        def __call__(self, output: Any) -> Any:
            return output[4:8, :].max()

    return _RawOutputOnly, _TopPredictionTarget


def _grayscale_cam(model: Any, canvas: npt.NDArray[np.uint8]) -> npt.NDArray[np.float64]:
    """The raw Grad-CAM heatmap (before overlaying/cropping) for one letterboxed image array."""
    import torch  # pylint: disable=import-outside-toplevel,import-error
    from pytorch_grad_cam import GradCAM  # pylint: disable=import-outside-toplevel,import-error

    raw_output_only, top_prediction_target = _grad_cam_helpers(torch)

    net = model.model
    net.eval()
    # ultralytics loads inference checkpoints with every parameter frozen (requires_grad=False)
    # by default; Grad-CAM needs gradients flowing back to the hooked activations, so this must
    # be re-enabled even though nothing is actually trained here (no optimizer step follows).
    net.requires_grad_(True)
    target_layers = [net.model[16], net.model[19], net.model[22]]  # P3/P4/P5

    input_tensor = torch.from_numpy(canvas).permute(2, 0, 1).float().unsqueeze(0) / 255.0
    with GradCAM(model=raw_output_only(net), target_layers=target_layers) as cam:
        result: npt.NDArray[np.float64] = cam(
            input_tensor=input_tensor, targets=[top_prediction_target()]
        )[0]
        return result


def _run_one(model: Any, name: str, image_path: Path, out_dir: Path, tag: str) -> None:
    """Grad-CAM overlay for one real image, saved as ``<out_dir>/<name>_<tag>.png``."""
    from pytorch_grad_cam.utils.image import (  # pylint: disable=import-outside-toplevel,import-error
        show_cam_on_image,
    )

    canvas, rgb, (content_h, content_w) = _load_letterboxed(image_path, IMGSZ)
    overlay = show_cam_on_image(rgb, _grayscale_cam(model, canvas), use_rgb=True)
    overlay = overlay[:content_h, :content_w]  # drop the grey letterbox padding strip
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay).save(out_dir / f"{name}_{tag}.png")


def main() -> None:
    """Parse arguments, run Grad-CAM on the fixed 11-image panel, save overlays."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--tag", required=True, help="suffix for output filenames, e.g. v5_scratch")
    parser.add_argument("--out", type=Path, default=Path("runs/gradcam_v3"))
    args = parser.parse_args()

    from ultralytics import YOLO  # pylint: disable=import-outside-toplevel,import-error

    model = YOLO(str(args.weights))
    missing: List[str] = []
    for name, image_path in PANEL:
        if not image_path.exists():
            missing.append(str(image_path))
            continue
        _run_one(model, name, image_path, args.out, args.tag)
    if missing:
        print(f"skipped {len(missing)} missing image(s): {missing}")
    print(f"done: {len(PANEL) - len(missing)} overlays -> {args.out}")


if __name__ == "__main__":
    main()
