"""Instance and semantic masks rasterised from a frame's annotations.

An annotation carrying ``mask_rle`` (rendered with ``--exact-labels``) contributes the engine's
exact visible
pixels, painted after all polygons; the rest are painted from polygons as follows.

Objects are painted far to near (by the forward distance in their ``box3d``; an annotation without
one counts as the farthest), so a nearer object covers a farther one. The polygons are mesh
silhouettes where an object has a real mesh and projected box hulls otherwise, so these masks are
polygon-accurate, not render-pass pixel-exact. Only labelled objects are painted: the "semantic"
mask holds object classes with 0 for everything else (road, buildings, vegetation, sky), so it is
not full-scene semantic segmentation.
"""

from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw
from pycocotools import mask as mask_utils

FAR = float("inf")


def _depth(annotation: Dict[str, Any]) -> float:
    box = annotation.get("box3d")
    return float(box["location"][2]) if box else FAR


def rasterise(  # pylint: disable=too-many-locals
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
    exact = [i for i, annotation in enumerate(annotations) if annotation.get("mask_rle")]
    for index in sorted(range(len(annotations)), key=lambda i: -_depth(annotations[i])):
        annotation = annotations[index]
        if annotation.get("mask_rle"):
            continue
        for polygon in annotation.get("segmentation", []):
            points = [(polygon[i], polygon[i + 1]) for i in range(0, len(polygon) - 1, 2)]
            if len(points) >= 3:
                draw_instance.polygon(points, fill=index + 1)
                draw_semantic.polygon(points, fill=int(annotation["category_id"]))
    instance_array = np.array(instance, dtype=np.uint16)
    semantic_array = np.array(semantic, dtype=np.uint8)
    for index in exact:
        rle = annotations[index]["mask_rle"]
        visible = (
            mask_utils.decode({"size": rle["size"], "counts": rle["counts"].encode("ascii")}) > 0
        )
        instance_array[visible] = index + 1
        semantic_array[visible] = int(annotations[index]["category_id"])
    return instance_array, semantic_array, table
