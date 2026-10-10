"""Build the leaf-cluster cards from photographed leaves (``content/T_LeafCluster*.png``).

``fetch_photo_textures.py`` downloads single-leaf photogrammetry atlases from ambientCG (CC0). This script
cuts each leaf out of its atlas using the atlas's opacity map, then scatters about 800 of them, turned and
scaled, over a rounded blob on a transparent 1024 x 1024 card, so a card shows a cluster of real leaves.
The tree generator (``src/procedural/foliage.py``) puts these cards on its canopy.

- ``T_LeafCluster.png``: green beech and hornbeam leaves (spring and summer).
- ``T_LeafClusterFall.png``: maple leaves in autumn colours (fall).

Colour is kept (it is the photograph's); the material multiplies it by a per-season tint that was
calibrated against real frames. Run with the project's Python after ``fetch_photo_textures.py``; the
output is committed.

    python unreal_plugin/tools/build_foliage_textures.py
"""

import math
from pathlib import Path
from typing import List, Sequence

import numpy as np
from PIL import Image
from scipy import ndimage

CONTENT = Path(__file__).resolve().parent.parent / "content"
PHOTO = CONTENT / "photo"
SIZE = 1024
LEAVES_PER_CARD = 800
LEAF_LENGTH_PX = (55.0, 90.0)  # about 6 to 11 cm on a 1.2 m card
MIN_LEAF_AREA_PX = 3000  # atlas leaves are far larger; this drops specks and fringe
CARDS = {
    "T_LeafCluster": ("LeafSet024", "LeafSet014"),
    "T_LeafClusterFall": ("LeafSet027",),
}


def cut_leaves(atlas_id: str) -> List[Image.Image]:
    """Every leaf of an atlas as an RGBA sprite cropped to its bounding box."""
    colour = Image.open(PHOTO / f"{atlas_id}_Color.jpg").convert("RGB")
    opacity = np.array(Image.open(PHOTO / f"{atlas_id}_Opacity.jpg").convert("L"))
    labels, count = ndimage.label(opacity > 128)
    sprites = []
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        mask = labels[box] == index
        if int(mask.sum()) < MIN_LEAF_AREA_PX:
            continue
        alpha = Image.fromarray((np.where(mask, opacity[box], 0)).astype(np.uint8), "L")
        sprite = colour.crop((box[1].start, box[0].start, box[1].stop, box[0].stop)).convert("RGBA")
        sprite.putalpha(alpha)
        sprites.append(sprite)
    print(atlas_id, "->", len(sprites), "leaves of", count, "components")
    return sprites


def build_card(sprites: Sequence[Image.Image], seed: int) -> Image.Image:
    """Scatter turned, scaled copies of ``sprites`` over a rounded blob; darker lower down."""
    rng = np.random.default_rng(seed)
    card = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for _ in range(LEAVES_PER_CARD):
        sprite = sprites[int(rng.integers(len(sprites)))]
        length = rng.uniform(*LEAF_LENGTH_PX)
        scale = length / max(sprite.size)
        leaf = sprite.resize(
            (max(2, int(sprite.width * scale)), max(2, int(sprite.height * scale))),
            Image.Resampling.LANCZOS,
        )
        leaf = leaf.rotate(
            float(rng.uniform(0.0, 360.0)), expand=True, resample=Image.Resampling.BICUBIC
        )
        radius = 0.43 * SIZE * math.sqrt(rng.random())
        angle = rng.uniform(0.0, 2.0 * math.pi)
        cx = 0.5 * SIZE + radius * math.cos(angle)
        cy = 0.5 * SIZE + radius * math.sin(angle)
        shade = rng.uniform(0.8, 1.05) * (0.85 + 0.15 * cy / SIZE)
        rgb = np.clip(np.array(leaf.convert("RGB")).astype(float) * shade, 0, 255).astype(np.uint8)
        shaded = Image.fromarray(rgb, "RGB").convert("RGBA")
        shaded.putalpha(leaf.getchannel("A"))
        card.alpha_composite(shaded, (int(cx - leaf.width / 2), int(cy - leaf.height / 2)))
    return card


def main() -> None:
    """Write both cluster cards."""
    for seed, (name, atlases) in enumerate(CARDS.items()):
        sprites = [sprite for atlas in atlases for sprite in cut_leaves(atlas)]
        card = build_card(sprites, 20261012 + seed)
        card.save(CONTENT / f"{name}.png", optimize=True)
        opaque = 100.0 * float((np.array(card.getchannel("A")) > 127).mean())
        print(f"wrote {name}.png: {opaque:.0f}% opaque")


if __name__ == "__main__":
    main()
