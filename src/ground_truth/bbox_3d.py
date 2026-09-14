"""3D bounding box extraction from generated buildings.

Implements MASTER_PROMPT Section 3.6's "Bounding Box extraction (3D...)"
bullet, informed by QOL_RESEARCH_CHECKLIST.md Section F.1's "3D boxes
valid geometry" check.

Buildings are already axis-aligned boxes (see
``building_placement.py``'s ``Building`` and ``mesh_factory.py``'s
extrusion), so extracting a 3D bounding box from one is a direct
dimension/center readout, not a fitting problem -- the interesting parts
of "bounding box extraction" in a real pipeline (fitting a box to an
arbitrary point cloud or mesh) don't arise here because the geometry was
generated as a box in the first place. This module exists to give that
readout a stable, documented shape (``BoundingBox3D``) for downstream
consumers (2D projection, export) rather than reaching into ``Building``
internals directly.
"""

from dataclasses import dataclass
from typing import List

import numpy as np
import numpy.typing as npt

from src.procedural.building_placement import Building


@dataclass(frozen=True)
class BoundingBox3D:
    """An axis-aligned 3D bounding box in world coordinates.

    Attributes
    ----------
    object_id : int
        Identifies the source object (``Building.building_id``).
    center : npt.NDArray[np.float64]
        [x, y, z] center of the box (z is half the object's height,
        since the object's own frame has its base at z=0).
    dimensions : npt.NDArray[np.float64]
        [length, width, height] extents, all positive.
    """

    object_id: int
    center: npt.NDArray[np.float64]
    dimensions: npt.NDArray[np.float64]

    def __post_init__(self) -> None:
        if not (self.dimensions > 0).all():
            raise ValueError(f"All dimensions must be positive, got {self.dimensions}")

    def corners(self) -> npt.NDArray[np.float64]:
        """The box's 8 corners, in world coordinates.

        Order matches ``mesh_factory.py``'s building mesh: 4 base corners
        (z = center.z - height/2) followed by 4 top corners
        (z = center.z + height/2), each going around the footprint
        counter-clockwise starting from (x_min, y_min).
        """
        half = self.dimensions / 2.0
        x_min, y_min, z_min = self.center - half
        x_max, y_max, z_max = self.center + half

        return np.array(
            [
                [x_min, y_min, z_min],
                [x_max, y_min, z_min],
                [x_max, y_max, z_min],
                [x_min, y_max, z_min],
                [x_min, y_min, z_max],
                [x_max, y_min, z_max],
                [x_max, y_max, z_max],
                [x_min, y_max, z_max],
            ]
        )


def extract_bbox_3d(building: Building) -> BoundingBox3D:
    """Extract a BoundingBox3D from one generated Building."""
    x_min, y_min, x_max, y_max = building.aabb
    length = x_max - x_min
    width = y_max - y_min
    height = building.height

    center = np.array([(x_min + x_max) / 2.0, (y_min + y_max) / 2.0, height / 2.0])
    dimensions = np.array([length, width, height])

    return BoundingBox3D(object_id=building.building_id, center=center, dimensions=dimensions)


def extract_bboxes_3d(buildings: List[Building]) -> List[BoundingBox3D]:
    """Extract a BoundingBox3D for every building in a scenario."""
    return [extract_bbox_3d(building) for building in buildings]
