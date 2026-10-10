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
CONTENT = Path(__file__).resolve().parent.parent / "content"
OUTPUT = CONTENT / "T_LeafCluster.png"
BARK_OUTPUT = CONTENT / "T_Bark.png"
GRASS_OUTPUT = CONTENT / "T_Grass.png"


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
    colour = Image.new("RGB", (scale, scale), (0, 0, 0))
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
        brightness = rng.uniform(95.0, 255.0) * (0.75 + 0.25 * (cy / scale))
        shift = rng.uniform(-1.0, 1.0)  # yellower or bluer, so the cluster is not one flat green
        fill = tuple(
            int(min(brightness * factor, 255.0))
            for factor in (1.0 + 0.07 * shift, 1.0, 1.0 - 0.10 * shift)
        )
        colour_draw.polygon(outline, fill=fill)
        alpha_draw.polygon(outline, fill=255)
        rib = [
            (cx - 0.5 * length * cos_h, cy - 0.5 * length * sin_h),
            (cx + 0.5 * length * cos_h, cy + 0.5 * length * sin_h),
        ]
        colour_draw.line(
            rib, fill=tuple(min(channel + 45, 255) for channel in fill), width=max(1, SUPERSAMPLE)
        )
    rgb = np.array(colour.resize((SIZE, SIZE), Image.Resampling.LANCZOS))
    mask = np.array(alpha.resize((SIZE, SIZE), Image.Resampling.LANCZOS))
    rgba = np.dstack([rgb, mask]).astype(np.uint8)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(OUTPUT, optimize=True)
    print(f"wrote {OUTPUT}: {SIZE}x{SIZE}, {100.0 * float((mask > 127).mean()):.0f}% opaque")


def stretched_noise(rng: np.random.Generator, size: int, across: float, along: float) -> np.ndarray:
    """Tileable noise in [0, 1] with features ``across`` pixels wide and ``along`` pixels tall."""
    spectrum = np.fft.fft2(rng.normal(size=(size, size)))
    fy = np.fft.fftfreq(size)[:, None] * along
    fx = np.fft.fftfreq(size)[None, :] * across
    field = np.real(np.fft.ifft2(spectrum * np.exp(-0.5 * (fx**2 + fy**2))))
    return (field - field.min()) / np.ptp(field)


def make_bark() -> None:
    """Furrowed bark: tall ridges, dark fissures along the low parts, fine speckle."""
    rng = np.random.default_rng(20261010)
    size = 512
    ridges = 0.6 * stretched_noise(rng, size, 14.0, 90.0) + 0.4 * stretched_noise(
        rng, size, 5.0, 30.0
    )
    fissure = np.clip((0.42 - ridges) / 0.42, 0.0, 1.0)  # the low parts are deep grooves
    speckle = stretched_noise(rng, size, 1.2, 2.5) * 0.15
    value = np.clip(0.30 + 0.6 * ridges - 0.3 * fissure + speckle, 0.0, 1.0)
    rgb = np.dstack([value * 1.06, value, value * 0.9])
    Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8), "RGB").save(BARK_OUTPUT)
    print(f"wrote {BARK_OUTPUT}")


def make_grass() -> None:
    """Tileable lawn: fine upright blade streaks over soft patches of lighter and darker grass."""
    rng = np.random.default_rng(20261011)
    size = 512
    patches = stretched_noise(rng, size, 30.0, 30.0)
    blades = 0.6 * stretched_noise(rng, size, 1.6, 7.0) + 0.4 * stretched_noise(
        rng, size, 3.0, 12.0
    )
    value = np.clip(0.25 + 0.45 * patches + 0.45 * blades, 0.0, 1.0)
    rgb = np.dstack([value * 0.92, value, value * 0.72])
    Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8), "RGB").save(GRASS_OUTPUT)
    print(f"wrote {GRASS_OUTPUT}")


if __name__ == "__main__":
    make_bark()
    make_grass()
    main()
