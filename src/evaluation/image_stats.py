"""Simple image statistics used to compare rendered frames with BDD100K val frames.

Brightness by band, colour, saturation, sharpness, clipping and JPEG blockiness, plus a picker
for BDD100K val images by their ``timeofday``/``weather`` labels. Used by
``bin/compare_image_stats.py`` and ``bin/calibrate_night.py`` to set the v7 lighting by
measurement.
"""

import glob
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
from PIL import Image
from scipy import ndimage

BDD_ROOT = Path("F:/datasets/bdd100k")
SIZE = (1280, 720)
BANDS = {"top": (0, 240), "mid": (240, 480), "bot": (480, 720)}
SAMPLE = 120


def image_stats(image: Image.Image) -> Dict[str, float]:
    """Brightness by band, colour, saturation, sharpness, clipping and JPEG blockiness."""
    pixels = np.asarray(
        image.convert("RGB").resize(SIZE, Image.Resampling.LANCZOS), dtype=np.float32
    )
    luma = 0.299 * pixels[..., 0] + 0.587 * pixels[..., 1] + 0.114 * pixels[..., 2]
    top, bottom = pixels.max(2), pixels.min(2)
    saturation = np.where(top > 8, (top - bottom) / np.maximum(top, 1), 0)
    lit = top > 40
    result = {f"luma_{name}": float(luma[a:b].mean()) for name, (a, b) in BANDS.items()}
    result["top_blue_over_red"] = float(
        pixels[:240, :, 2].mean() / max(float(pixels[:240, :, 0].mean()), 1.0)
    )
    result["saturation_lit"] = float(saturation[lit].mean()) if lit.any() else 0.0
    result["laplacian_var"] = float(ndimage.laplace(luma).var())
    result["share_ge_250"] = float((luma >= 250).mean())
    result["share_lt_10"] = float((luma < 10).mean())
    step = np.abs(np.diff(luma, axis=1))
    result["jpeg_blockiness"] = float(step[:, 7::8].mean() / max(float(step.mean()), 1e-6))
    return result


def mean_stats(rows: List[Dict[str, float]]) -> Dict[str, float]:
    """The mean of each statistic over ``rows``."""
    return {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}


def bdd_names(timeofday: str, weather: str = "") -> List[str]:
    """Names of BDD100K val images with the attributes (weather optional)."""
    names = []
    for path in sorted(glob.glob(str(BDD_ROOT / "labels/100k/val/*.json"))):
        label = json.loads(Path(path).read_text(encoding="utf-8"))
        attributes = label["attributes"]
        if attributes.get("timeofday") == timeofday and weather in ("", attributes.get("weather")):
            names.append(label["name"])
    return names
