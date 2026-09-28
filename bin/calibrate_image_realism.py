"""Find realism-post-process parameters by measurement, not guessing.

Tries a small grid of (blur sigma, saturation scale, noise std, JPEG quality) on a sample of
synthetic renders, measures the resulting Laplacian variance / mean saturation / JPEG
block-boundary score / high-frequency residual std, and prints how close each candidate lands
to the real-benchmark targets measured earlier (BDD100K, Cityscapes; see EXPERIMENT_LOG.md).
Pick the parameters from whichever row lands closest, then pass them to
``apply_image_realism.py``.

    PYTHONPATH=. python bin/calibrate_image_realism.py --dataset live_dataset/train2000_v3 \\
        --sample-size 40
"""

import argparse
import io
import random
from pathlib import Path
from typing import List, Tuple

import numpy as np
import numpy.typing as npt
from PIL import Image
from scipy.ndimage import gaussian_filter, laplace

# Measured against 300 real images each, resized to 960px longest side (matching training
# imgsz, since that is the resolution the network actually sees -- see
# EXPERIMENT_LOG.md's post-v3 diagnostic section).
TARGETS = {
    "laplacian_var": 260.0,  # BDD 279.3, Cityscapes 240.2
    "saturation_mean": 70.0,  # BDD 73.8, Cityscapes 49.3 (splitting the difference)
    "block_score": 1.4,  # BDD 1.863, Cityscapes 1.001 (BDD-specific; moderate middle ground)
    "residual_std": 4.7,  # BDD 4.69, Cityscapes 4.78
}
TRAIN_IMGSZ = 960


def _resize_longest_side(image: Image.Image, longest: int) -> Image.Image:
    """``image`` scaled so its longest side is exactly ``longest`` pixels."""
    scale = longest / max(image.size)
    size = (round(image.size[0] * scale), round(image.size[1] * scale))
    return image.resize(size, Image.Resampling.BILINEAR)


def _laplacian_variance(gray: npt.NDArray[np.float64]) -> float:
    """A blur/sharpness proxy: variance of the Laplacian response."""
    return float(laplace(gray.astype(np.float64)).var())


def _block_score(gray: npt.NDArray[np.float64]) -> float:
    """Ratio of mean gradient magnitude at 8-pixel-boundary rows/cols vs elsewhere."""
    dy = np.abs(np.diff(gray.astype(np.float64), axis=0))
    dx = np.abs(np.diff(gray.astype(np.float64), axis=1))
    on_y, off_y = dy[7::8, :], np.delete(dy, np.arange(7, dy.shape[0], 8), axis=0)
    on_x, off_x = dx[:, 7::8], np.delete(dx, np.arange(7, dx.shape[1], 8), axis=1)
    on = np.concatenate([on_y.ravel(), on_x.ravel()])
    off = np.concatenate([off_y.ravel(), off_x.ravel()])
    return float(on.mean() / max(off.mean(), 1e-6))


def _residual_std(gray: npt.NDArray[np.float64]) -> float:
    """Std of (image - mild Gaussian blur of it): a noise/high-frequency-energy proxy."""
    blurred = gaussian_filter(gray.astype(np.float64), sigma=1.0)
    return float((gray.astype(np.float64) - blurred).std())


def _process(
    image: Image.Image, blur_sigma: float, sat_scale: float, noise_std: float, jpeg_quality: int
) -> Image.Image:
    """Apply one candidate parameter set to one image."""
    hsv = np.array(image.convert("HSV"), dtype=np.float64)
    hsv[..., 1] = np.clip(hsv[..., 1] * sat_scale, 0, 255)
    desaturated = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")
    arr = np.array(desaturated, dtype=np.float64)
    for channel in range(3):
        arr[..., channel] = gaussian_filter(arr[..., channel], sigma=blur_sigma)
    if noise_std > 0:
        arr += np.random.default_rng(0).normal(0, noise_std, arr.shape)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    blurred = Image.fromarray(arr, "RGB")
    buffer = io.BytesIO()
    blurred.save(buffer, format="JPEG", quality=jpeg_quality)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def _measure(image: Image.Image) -> Tuple[float, float, float, float]:
    """(laplacian_var, saturation_mean, block_score, residual_std) for one image."""
    gray = np.array(image.convert("L"), dtype=np.float64)
    saturation = np.array(image.convert("HSV"), dtype=np.float64)[..., 1].mean()
    return (_laplacian_variance(gray), saturation, _block_score(gray), _residual_std(gray))


def main() -> None:
    """Parse arguments, try a parameter grid, print measured results vs targets."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    paths: List[Path] = sorted((args.dataset / "images").glob("*.png"))
    sample = random.Random(args.seed).sample(paths, min(args.sample_size, len(paths)))
    images = [_resize_longest_side(Image.open(p).convert("RGB"), TRAIN_IMGSZ) for p in sample]

    baseline = np.array([_measure(image) for image in images]).mean(axis=0)
    print(
        f"baseline (unmodified): lap_var={baseline[0]:.1f} sat={baseline[1]:.1f} "
        f"block={baseline[2]:.3f} residual={baseline[3]:.2f}"
    )
    print(
        f"targets:               lap_var={TARGETS['laplacian_var']:.1f} "
        f"sat={TARGETS['saturation_mean']:.1f} block={TARGETS['block_score']:.3f} "
        f"residual={TARGETS['residual_std']:.2f}"
    )
    print()

    grid = [
        (blur, sat, noise, quality)
        for blur in (0.0, 0.2, 0.4, 0.6, 0.8)
        for sat in (0.75,)
        for noise in (0.0, 3.0)
        for quality in (75, 90)
    ]
    for blur_sigma, sat_scale, noise_std, jpeg_quality in grid:
        processed = [
            _process(image, blur_sigma, sat_scale, noise_std, jpeg_quality) for image in images
        ]
        measured = np.array([_measure(image) for image in processed]).mean(axis=0)
        print(
            f"blur={blur_sigma:.1f} sat={sat_scale:.2f} noise={noise_std:.1f} "
            f"jpeg={jpeg_quality:3d}  ->  lap_var={measured[0]:6.1f} sat={measured[1]:5.1f} "
            f"block={measured[2]:.3f} residual={measured[3]:.2f}"
        )


if __name__ == "__main__":
    main()
