"""Instance and semantic masks rasterised from a frame's annotation polygons.

Objects are painted far to near (by the forward distance in their ``box3d``; an annotation without
one counts as the farthest), so a nearer object covers a farther one. The polygons are mesh
silhouettes where an object has a real mesh and projected box hulls otherwise, so these masks are
polygon-accurate, not render-pass pixel-exact.
"""

from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw

FAR = float("inf")


def _depth(annotation: Dict[str, Any]) -> float:
    box = annotation.get("box3d")
    return float(box["location"][2]) if box else FAR


def rasterise(
    annotations: Sequence[Dict[str, Any]], size: Tuple[int, int]
) -> Tuple[npt.NDArray[np.uint16], npt.NDArray[np.uint8], List[Dict[str, int]]]:
    """(instance mask, semantic mask, instance table) for one image of ``size`` = (width, height).

    Instance values are 1, 2, ... in the order of ``annotations`` (0 is background); the table maps
    each to its annotation id and category id. Semantic values are the COCO category ids (0 is
    background).
    """
    width, height = size
    instance = Image.new("I", (width, height), 0)
    semantic = Image.new("L", (width, height), 0)
    draw_instance, draw_semantic = ImageDraw.Draw(instance), ImageDraw.Draw(semantic)
    table = [
        {
            "instance": index + 1,
            "annotation_id": int(annotation["id"]),
            "category_id": int(annotation["category_id"]),
        }
        for index, annotation in enumerate(annotations)
    ]
    for index in sorted(range(len(annotations)), key=lambda i: -_depth(annotations[i])):
        annotation = annotations[index]
        for polygon in annotation.get("segmentation", []):
            points = [(polygon[i], polygon[i + 1]) for i in range(0, len(polygon) - 1, 2)]
            if len(points) >= 3:
                draw_instance.polygon(points, fill=index + 1)
                draw_semantic.polygon(points, fill=int(annotation["category_id"]))
    return np.asarray(instance, dtype=np.uint16), np.asarray(semantic, dtype=np.uint8), table
