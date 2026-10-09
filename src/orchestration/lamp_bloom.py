"""Camera glare around vehicle lamps, added in image space.

The engine draws each lamp as a small emissive disc. Its night colour grading desaturates everything
(global saturation 0.4), so the discs come out pale pink and crisp, while in real dash-cam frames a
taillight is a saturated red glare: a bright, nearly clipped core inside a soft red halo, because
the lens and sensor spread light from very bright points. This adds that glare.

Each lamp is projected into the frame from the scenario's own lamp positions; it takes part only if
the engine's exact depth map shows the lamp itself at its pixel (so a lamp hidden behind a car adds
nothing). The glare is a sum of three Gaussians around the lamp, added in linear light with the
lamp's colour and clipped, so a strong lamp ends in a pink-white core inside a deep red halo. Pixels
under the painted hood are left alone.

The tail-lamp widths and strengths are fitted to real BDD100K night frames
(``scripts/calibrate_bloom.py``, ``EXPERIMENT_LOG.md``): among cars with visible lamps, the lamp
area, blob radius and the saturation of the deep red match real to within a few percent. The
headlamp strength is not fitted. This is a camera effect added to the engine's picture, and the
dataset card says so.
"""

import dataclasses
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural import night_lights
from src.sensors.camera_model import Camera

GAMMA = 2.2


@dataclasses.dataclass(frozen=True)
class BloomParams:  # pylint: disable=too-many-instance-attributes
    """Shape and strength of the glare, in lamp radii and linear radiance (1.0 = display white)."""

    sigma_radii: Tuple[float, float, float] = (0.4, 1.0, 2.8)
    weights: Tuple[float, float, float] = (1.0, 0.35, 0.08)
    brake_peak: float = 2.0
    running_peak: float = 0.5
    head_peak: float = 0.4
    min_sigma_px: float = 1.2
    max_radius_px: float = 600.0  # safety bound only: 4 sigma already holds under 0.04% of the peak
    depth_tolerance_m: float = 0.6


@dataclasses.dataclass(frozen=True)
class Lamp:
    """A visible lamp in image coordinates."""

    u: float
    v: float
    radius_px: float
    colour: Tuple[float, float, float]
    peak: float


def _kind_peak(
    glow: Dict[str, Any], params: BloomParams
) -> Tuple[Tuple[float, float, float], float]:
    """Glare colour and peak for a glow entry: red tail lamps (brake brighter) or headlamps."""
    colour = tuple(float(c) for c in glow["color"])
    if colour[1] < 0.3:  # red: a tail lamp
        braking = glow["intensity"] >= 0.99 * night_lights.BRAKE_LIGHT_GLOW_INTENSITY
        return (1.0, 0.05, 0.03), params.brake_peak if braking else params.running_peak
    return (1.0, 0.93, 0.80), params.head_peak


def visible_lamps(  # pylint: disable=too-many-locals
    glows: Sequence[Dict[str, Any]],
    camera: Camera,
    depth_m: npt.NDArray[np.float32],
    params: BloomParams = BloomParams(),
) -> List[Lamp]:
    """The glows that are in front of the camera, in the frame and not hidden, as image lamps."""
    height, width = depth_m.shape
    focal = float(camera.intrinsics.get_intrinsic_matrix()[0, 0])
    lamps: List[Lamp] = []
    for glow in glows:
        pixel, depth = camera.project(np.asarray(glow["position"], dtype=np.float64))
        if pixel is None or not (0 <= pixel[0] < width and 0 <= pixel[1] < height):
            continue
        u, v = int(pixel[0]), int(pixel[1])
        seen = float(depth_m[v, u])
        if seen <= 0 or abs(seen - depth) > params.depth_tolerance_m:
            continue
        semi = glow["semi_axes_m"]
        radius = focal * float(np.sqrt(semi[1] * semi[2])) / depth
        colour, peak = _kind_peak(glow, params)
        lamps.append(Lamp(float(pixel[0]), float(pixel[1]), radius, colour, peak))
    return lamps


def add_glare(  # pylint: disable=too-many-locals
    image: npt.NDArray[np.uint8],
    lamps: Sequence[Lamp],
    params: BloomParams = BloomParams(),
    keep: Optional[npt.NDArray[np.bool_]] = None,
) -> npt.NDArray[np.uint8]:
    """``image`` with the glare of ``lamps`` added; pixels where ``keep`` is True are unchanged."""
    height, width = image.shape[:2]
    linear = (image.astype(np.float32) / 255.0) ** GAMMA
    added = np.zeros_like(linear)
    for lamp in lamps:
        sigmas = [max(params.min_sigma_px, s * lamp.radius_px) for s in params.sigma_radii]
        reach = int(min(params.max_radius_px, 4.0 * max(sigmas)))
        x0, x1 = max(0, int(lamp.u) - reach), min(width, int(lamp.u) + reach + 1)
        y0, y1 = max(0, int(lamp.v) - reach), min(height, int(lamp.v) + reach + 1)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        radius_sq = (xx - lamp.u) ** 2 + (yy - lamp.v) ** 2
        profile = sum(
            w * np.exp(-radius_sq / (2.0 * s**2)) for w, s in zip(params.weights, sigmas)
        )
        added[y0:y1, x0:x1] += (lamp.peak * profile)[..., None] * np.asarray(
            lamp.colour, np.float32
        )
    out = np.clip(linear + added, 0.0, 1.0) ** (1.0 / GAMMA)
    result: npt.NDArray[np.uint8] = np.rint(out * 255.0).astype(np.uint8)
    if keep is not None:
        result[keep] = image[keep]
    return result
