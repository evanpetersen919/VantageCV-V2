"""Generate the leaf-cluster texture the foliage materials use (``content/T_LeafCluster.png``).

A cluster of about 300 pointed-oval leaves with a lighter midrib on a transparent background, drawn
here with numpy and Pillow, so the texture has no third-party origin. Colour is only brightness
(grey): the season's tint is applied by the material. Run with the project's Python; the output
is committed.

    python unreal_plugin/tools/make_leaf_texture.py
"""

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SIZE = 512
SUPERSAMPLE = 2
LEAVES = 300
LEAF_LENGTH_PX = (46.0, 70.0)
LEAF_ASPECT = (0.38, 0.5)
OUTPUT = Path(__file__).resolve().parent.parent / "content" / "T_LeafCluster.png"


def leaf_polygon(length: float, width: float, steps: int = 14) -> list:
    """Outline of a pointed oval of the given size centred on the origin, pointing along +x."""
    top = [
        (length * (t / steps - 0.5), 0.5 * width * math.sin(math.pi * (t / steps) ** 0.8))
        for t in range(steps + 1)
    ]
    return top + [(x, -y) for x, y in reversed(top)]


def main() -> None:  # pylint: disable=too-many-locals
    """Draw the cluster and write the PNG."""
    rng = np.random.default_rng(20261009)
    scale = SIZE * SUPERSAMPLE
    colour = Image.new("L", (scale, scale), 0)
    alpha = Image.new("L", (scale, scale), 0)
    colour_draw, alpha_draw = ImageDraw.Draw(colour), ImageDraw.Draw(alpha)
    for _ in range(LEAVES):
        # Leaves cover a rounded blob so the card's edge is ragged and its corners are empty.
        radius = 0.46 * scale * math.sqrt(rng.random())
        angle = rng.uniform(0.0, 2.0 * math.pi)
        cx = 0.5 * scale + radius * math.cos(angle)
        cy = 0.5 * scale + radius * math.sin(angle)
        length = rng.uniform(*LEAF_LENGTH_PX) * SUPERSAMPLE
        width = length * rng.uniform(*LEAF_ASPECT)
        heading = rng.uniform(0.0, 2.0 * math.pi)
        cos_h, sin_h = math.cos(heading), math.sin(heading)
        outline = [
            (cx + x * cos_h - y * sin_h, cy + x * sin_h + y * cos_h)
            for x, y in leaf_polygon(length, width)
        ]
        brightness = int(rng.uniform(95.0, 255.0) * (0.75 + 0.25 * (cy / scale)))
        colour_draw.polygon(outline, fill=min(brightness, 255))
        alpha_draw.polygon(outline, fill=255)
        rib = [
            (cx - 0.5 * length * cos_h, cy - 0.5 * length * sin_h),
            (cx + 0.5 * length * cos_h, cy + 0.5 * length * sin_h),
        ]
        colour_draw.line(rib, fill=min(brightness + 45, 255), width=max(1, SUPERSAMPLE))
    grey = np.array(colour.resize((SIZE, SIZE), Image.Resampling.LANCZOS))
    mask = np.array(alpha.resize((SIZE, SIZE), Image.Resampling.LANCZOS))
    rgba = np.dstack([grey, grey, grey, mask]).astype(np.uint8)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(OUTPUT, optimize=True)
    print(f"wrote {OUTPUT}: {SIZE}x{SIZE}, {100.0 * float((mask > 127).mean()):.0f}% opaque")


if __name__ == "__main__":
    main()
