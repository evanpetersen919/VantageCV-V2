"""README figures built from a rendered live dataset (needs the semantic maps and exact masks).

    PYTHONPATH=. python scripts/make_figures.py live_dataset/kaggle_v1 --out docs/images

Writes ``layers_strip.jpg`` (RGB, class map, depth and instance masks of one frame),
``annotation_grid.jpg`` (boxes, masks and 3D boxes on frames from different conditions) and
``conditions_sheet.jpg`` (one frame per time of day and weather found in the dataset).
"""

import argparse
import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from matplotlib import colormaps
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont
from pycocotools import mask as mask_utils

from src.orchestration.semantic_labels import colorize

CATEGORY_COLOUR = {1: (255, 60, 60), 3: (60, 200, 255), 6: (255, 200, 0), 8: (180, 90, 255)}
CUBOID_EDGES = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
]
NEAR_PLANE_M = 0.1
DEPTH_RANGE_M = 80.0
TILE = (960, 540)
Annotation = Dict[str, Any]
Rgb = NDArray[np.uint8]


def _font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    """Arial where the system has it, else Pillow's built-in face."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def load_parts(root: Path) -> Tuple[List[Annotation], Dict[int, List[Annotation]]]:
    """All images of a live dataset and their annotations keyed by image id."""
    images: List[Annotation] = []
    by_image: Dict[int, List[Annotation]] = {}
    for part in sorted(glob.glob(str(root / "parts" / "scenario_*.json"))):
        data = json.loads(Path(part).read_text(encoding="utf-8"))
        images += data["images"]
        for annotation in data["annotations"]:
            by_image.setdefault(annotation["image_id"], []).append(annotation)
    return images, by_image


def _decode(rle: Annotation) -> NDArray[np.bool_]:
    """The boolean mask of one stored run-length mask."""
    counts = rle["counts"].encode("ascii")
    return np.asarray(mask_utils.decode({"size": rle["size"], "counts": counts})) > 0


def _caption(picture: Image.Image, text: str) -> Image.Image:
    """``picture`` with a black caption bar across the top."""
    draw = ImageDraw.Draw(picture)
    draw.rectangle([0, 0, picture.width, 46], fill=(0, 0, 0))
    draw.text((12, 6), text, fill=(255, 255, 255), font=_font(32))
    return picture


def class_map_panel(root: Path, image: Annotation) -> Image.Image:
    """The full-scene class map in Cityscapes colours."""
    classes = np.array(Image.open(root / image["semantic_file"]))
    return Image.fromarray(colorize(classes))


def depth_panel(root: Path, image: Annotation) -> Image.Image:
    """Metric depth in turbo colours (0-80 m); black where there is no depth (sky, hood)."""
    depth = (
        np.array(Image.open(root / image["depth_file"])).astype(np.float64) / image["depth_scale"]
    )
    colours = (colormaps["turbo"](np.clip(depth / DEPTH_RANGE_M, 0, 1))[..., :3] * 255).astype(
        np.uint8
    )
    colours[depth == 0] = 0
    return Image.fromarray(colours)


def mask_panel(rgb: Rgb, annotations: Sequence[Annotation]) -> Image.Image:
    """The photo with every exact instance mask tinted in the class colour, plus its 2D box."""
    tinted = rgb.astype(np.float64)
    for annotation in annotations:
        colour = np.array(CATEGORY_COLOUR[annotation["category_id"]])
        region = _decode(annotation["mask_rle"])
        tinted[region] = 0.45 * tinted[region] + 0.55 * colour
    picture = Image.fromarray(tinted.astype(np.uint8))
    draw = ImageDraw.Draw(picture)
    for annotation in annotations:
        x, y, w, h = annotation["bbox"]
        draw.rectangle(
            [x, y, x + w, y + h], outline=CATEGORY_COLOUR[annotation["category_id"]], width=3
        )
    return picture


def _cuboid_corners(box3d: Annotation) -> NDArray[np.float64]:
    """The eight corners (rows) of a KITTI-convention box in the camera frame."""
    height, width, length = box3d["dimensions_hwl"]
    x = [length / 2, length / 2, -length / 2, -length / 2] * 2
    y = [0, 0, 0, 0, -height, -height, -height, -height]
    z = [width / 2, -width / 2, -width / 2, width / 2] * 2
    c, s = np.cos(box3d["rotation_y"]), np.sin(box3d["rotation_y"])
    rotation = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.asarray((rotation @ np.array([x, y, z]) + np.array(box3d["location"])[:, None]).T)


def cuboid_panel(rgb: Rgb, image: Annotation, annotations: Sequence[Annotation]) -> Image.Image:
    """The photo with the 3D box of every object, projected with the image's ``kitti_P2``."""
    picture = Image.fromarray(rgb)
    draw = ImageDraw.Draw(picture)
    projection = np.array(image["kitti_P2"]).reshape(3, 4)

    def project(point: NDArray[np.float64]) -> Tuple[float, float]:
        pixel = projection @ np.append(point, 1.0)
        return float(pixel[0] / pixel[2]), float(pixel[1] / pixel[2])

    for annotation in annotations:
        corners = _cuboid_corners(annotation["box3d"])
        for first, second in CUBOID_EDGES:
            p0, p1 = corners[first], corners[second]
            if p0[2] < NEAR_PLANE_M and p1[2] < NEAR_PLANE_M:
                continue
            if p0[2] < NEAR_PLANE_M:
                p0 = p0 + (p1 - p0) * (NEAR_PLANE_M - p0[2]) / (p1[2] - p0[2])
            if p1[2] < NEAR_PLANE_M:
                p1 = p1 + (p0 - p1) * (NEAR_PLANE_M - p1[2]) / (p0[2] - p1[2])
            draw.line(
                [project(p0), project(p1)], fill=CATEGORY_COLOUR[annotation["category_id"]], width=3
            )
    return picture


def _grid(tiles: Sequence[Image.Image], columns: int) -> Image.Image:
    """``tiles`` pasted row by row, each resized to the standard tile size."""
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (TILE[0] * columns, TILE[1] * rows))
    for k, tile in enumerate(tiles):
        sheet.paste(
            tile.resize(TILE, Image.Resampling.LANCZOS),
            ((k % columns) * TILE[0], (k // columns) * TILE[1]),
        )
    return sheet


def _rich(
    images: Sequence[Annotation], by_image: Dict[int, List[Annotation]], **wanted: str
) -> Optional[Annotation]:
    """The ``wanted`` frame with the most distinct classes, then the most objects."""
    matches = [
        i
        for i in images
        if "semantic_file" in i
        and all(i.get(key) == value for key, value in wanted.items())
        and by_image.get(i["id"])
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda i: (len({a["category_id"] for a in by_image[i["id"]]}), len(by_image[i["id"]])),
    )


def layers_strip(
    root: Path, image: Annotation, annotations: Sequence[Annotation], destination: Path
) -> None:
    """RGB, class map, depth and instance masks of one frame in a 2 x 2 sheet."""
    rgb = np.array(Image.open(root / image["file_name"]).convert("RGB"))
    tiles = [
        _caption(Image.fromarray(rgb.copy()), "Rendered image"),
        _caption(class_map_panel(root, image), "Class map (Cityscapes ids)"),
        _caption(depth_panel(root, image), "Metric depth (0-80 m)"),
        _caption(mask_panel(rgb, annotations), "Exact instance masks and 2D boxes"),
    ]
    _grid(tiles, 2).save(destination, quality=88)


def annotation_grid(
    root: Path, frames: Sequence[Tuple[Annotation, Sequence[Annotation]]], destination: Path
) -> None:
    """Six frames with masks, boxes and 3D boxes, each labelled with its conditions."""
    tiles = []
    for image, annotations in frames:
        rgb = np.array(Image.open(root / image["file_name"]).convert("RGB"))
        picture = cuboid_panel(np.array(mask_panel(rgb, annotations)), image, annotations)
        tiles.append(
            _caption(picture, f"{image['time_of_day']}, {image['weather']}, {image['season']}")
        )
    _grid(tiles, 2).save(destination, quality=88)


def conditions_sheet(root: Path, frames: Sequence[Annotation], destination: Path) -> None:
    """One plain frame for each condition found, labelled."""
    tiles = []
    for image in frames:
        picture = Image.open(root / image["file_name"]).convert("RGB")
        tiles.append(_caption(picture, f"{image['time_of_day']} / {image['weather']}"))
    _grid(tiles, 3).save(destination, quality=88)


def main() -> None:
    """Pick representative frames from a dataset and write the figures."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    images, by_image = load_parts(args.root)
    args.out.mkdir(parents=True, exist_ok=True)

    hero = _rich(images, by_image, time_of_day="day", weather="clear")
    if hero is None:
        raise SystemExit("error: no clear daytime frame with semantic maps in this dataset")
    layers_strip(args.root, hero, by_image[hero["id"]], args.out / "layers_strip.jpg")

    conditions: Dict[Tuple[str, str], Annotation] = {}
    for image in images:
        key = (image["time_of_day"], image["weather"])
        best = _rich(images, by_image, time_of_day=key[0], weather=key[1])
        if best is not None:
            conditions[key] = best
    ordered = [conditions[key] for key in sorted(conditions)]
    print("conditions found:", sorted(conditions))
    conditions_sheet(args.root, ordered[:9], args.out / "conditions_sheet.jpg")
    annotation_grid(
        args.root, [(i, by_image[i["id"]]) for i in ordered[:6]], args.out / "annotation_grid.jpg"
    )


if __name__ == "__main__":
    main()
