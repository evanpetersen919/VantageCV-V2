"""Polygons traced from a mask follow it pixel for pixel."""

# pylint: disable=missing-function-docstring

import numpy as np
from pycocotools import mask as mask_utils

from src.export.mask_polygons import mask_to_polygons


def _raster(polygons: list, shape: tuple) -> np.ndarray:
    return mask_utils.decode(mask_utils.merge(mask_utils.frPyObjects(polygons, *shape))) > 0


def test_rectangle_is_four_vertices_and_exact() -> None:
    mask = np.zeros((20, 30), dtype=bool)
    mask[3:12, 5:17] = True
    polygons = mask_to_polygons(mask)
    assert len(polygons) == 1 and len(polygons[0]) == 8
    assert (_raster(polygons, mask.shape) == mask).all()


def test_an_l_shape_and_a_blob_are_pixel_exact() -> None:
    shape = np.zeros((50, 40), dtype=bool)
    shape[5:40, 5:12] = True
    shape[33:40, 5:30] = True
    yy, xx = np.mgrid[:50, :40]
    blob = ((yy - 25) ** 2 / 200 + (xx - 20) ** 2 / 120) < 1
    for mask in (shape, blob):
        polygons = mask_to_polygons(mask)
        assert len(polygons) == 1
        assert (_raster(polygons, mask.shape) == mask).all()


def test_regions_touching_at_a_corner_are_separate_polygons() -> None:
    mask = np.zeros((20, 20), dtype=bool)
    mask[2:6, 2:6] = True
    mask[6:10, 6:10] = True
    mask[10:14, 10:14] = True
    assert len(mask_to_polygons(mask)) == 3


def test_a_hole_is_covered_by_the_outer_polygon_and_an_empty_mask_gives_nothing() -> None:
    mask = np.zeros((20, 20), dtype=bool)
    mask[2:18, 2:18] = True
    mask[8:12, 8:12] = False
    polygons = mask_to_polygons(mask)
    assert len(polygons) == 1
    assert (
        _raster(polygons, mask.shape).sum() == 16 * 16
    )  # holes are not representable in a COCO polygon
    assert not mask_to_polygons(np.zeros((5, 5), dtype=bool))
