"""Apply the calibrated realism post-process to a whole live dataset (images only).

Desaturates, mildly blurs and JPEG-recompresses every image, closing the measured
sharpness/saturation/compression gap against BDD100K and Cityscapes (see
``bin/calibrate_image_realism.py`` and ``EXPERIMENT_LOG.md``'s v4a entry for how these
defaults were chosen: the closest simultaneous match to all four measured real-image targets
among the tested grid). Annotations, splits and YOLO labels are untouched -- this only
rewrites pixels, so run ``split_dataset.py``/label export against the *source* dataset's
train.json/val.json and this script's output images, or just copy the label side over.

    PYTHONPATH=. python bin/apply_image_realism.py --dataset live_dataset/train2000_v3 \\
        --out live_dataset/train2000_v4a
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

BLUR_SIGMA = 0.4
SATURATION_SCALE = 0.75
JPEG_QUALITY = 75


def _repoint_to_jpg(data: Dict[str, Any]) -> Dict[str, Any]:
    """``data`` with every image's ``file_name`` repointed from ``.png`` to ``.jpg``."""
    for image in data.get("images", []):
        image["file_name"] = str(Path(image["file_name"]).with_suffix(".jpg"))
    return data


def _process(image: Image.Image) -> Image.Image:
    """The calibrated desaturate + blur + JPEG-recompress pass, applied in place of memory."""
    hsv = np.array(image.convert("HSV"), dtype=np.float64)
    hsv[..., 1] = np.clip(hsv[..., 1] * SATURATION_SCALE, 0, 255)
    desaturated = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")
    arr = np.array(desaturated, dtype=np.float64)
    for channel in range(3):
        arr[..., channel] = gaussian_filter(arr[..., channel], sigma=BLUR_SIGMA)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def main() -> None:
    """Parse arguments, copy non-image files, process every image."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("annotations.json", "train.json", "val.json"):
        source = args.dataset / name
        if not source.exists():
            continue
        data = _repoint_to_jpg(json.loads(source.read_text(encoding="utf-8")))
        (args.out / name).write_text(json.dumps(data), encoding="utf-8")
    for name in ("split.json", "manifest.json"):
        source = args.dataset / name
        if source.exists():
            shutil.copy2(source, args.out / name)

    (args.out / "images").mkdir(parents=True, exist_ok=True)
    sources = sorted((args.dataset / "images").glob("*.png"))
    for index, source in enumerate(sources):
        image = Image.open(source).convert("RGB")
        processed = _process(image)
        destination = (args.out / "images" / source.name).with_suffix(".jpg")
        processed.save(destination, format="JPEG", quality=JPEG_QUALITY)
        if (index + 1) % 200 == 0:
            print(f"{index + 1}/{len(sources)}")
    print(f"done: {len(sources)} images -> {args.out / 'images'}")


if __name__ == "__main__":
    main()
