"""3D bounding box extraction from generated buildings, vehicles, and
pedestrians.

Implements MASTER_PROMPT Section 3.6's "Bounding Box extraction (3D...)"
bullet, informed by QOL_RESEARCH_CHECKLIST.md Section F.1's "3D boxes
valid geometry" check.

Every object this pipeline generates is already a (possibly rotated) box
in its own generator (``Building``, ``Vehicle``, ``Pedestrian`` --
see ``building_placement.py``, ``actor_placement.py``), so extracting a
3D bounding box is a direct dimension/center/heading readout, not a
fitting problem -- the interesting parts of "bounding box extraction" in
a real pipeline (fitting a box to an arbitrary point cloud or mesh)
don't arise here. This module exists to give that readout a stable,
documented shape (``BoundingBox3D``) for downstream consumers (2D
projection, export) rather than reaching into each generator's own
object internals directly.
"""

from dataclasses import dataclass
from typing import List

import numpy as np
import numpy.typing as npt

from src.ground_truth.categories import BUILDING, PEDESTRIAN, VEHICLE_TYPE_TO_CATEGORY
from src.procedural.actor_placement import Pedestrian, Vehicle
from src.procedural.building_placement import Building


@dataclass(frozen=True)
class BoundingBox3D:
    """A 3D bounding box in world coordinates, optionally rotated about
    its vertical (z) axis.

    Attributes
    ----------
    object_id : int
        Identifies the source object (e.g. ``Building.building_id``,
        ``Vehicle.vehicle_id``).
    center : npt.NDArray[np.float64]
        [x, y, z] center of the box (z is half the object's height,
        since every generator's own frame has its base at z=0).
    dimensions : npt.NDArray[np.float64]
        [length, width, height] extents, all positive. "Length" is along
        the box's own local x-axis before ``heading_rad`` is applied.
    heading_rad : float
        Rotation about the z-axis, in radians, applied to the footprint
        (length/width) only -- height is unaffected by definition.
        Default 0.0 (axis-aligned, world x/y == local length/width),
        matching every prior release's behavior for buildings exactly.
    category_id : int
        See ``src.ground_truth.categories``. Defaults to
        :data:`src.ground_truth.categories.BUILDING` for backward
        compatibility with every existing caller that never set this.
    """

    object_id: int
    center: npt.NDArray[np.float64]
    dimensions: npt.NDArray[np.float64]
    heading_rad: float = 0.0
    category_id: int = BUILDING

    def __post_init__(self) -> None:
        if not (self.dimensions > 0).all():
            raise ValueError(f"All dimensions must be positive, got {self.dimensions}")

    def corners(self) -> npt.NDArray[np.float64]:
        """The box's 8 corners, in world coordinates.

        Order matches ``mesh_factory.py``'s box mesh: 4 base corners
        (z = center.z - height/2) followed by 4 top corners
        (z = center.z + height/2), each going around the footprint
        counter-clockwise starting from the local (-length/2, -width/2)
        corner, then rotated by ``heading_rad`` about the center and
        translated to ``center``.

        For ``heading_rad == 0.0`` (every building, always), this is
        exactly the axis-aligned box every prior release computed --
        the rotation matrix is the identity in that case.
        """
        half = self.dimensions / 2.0
        length_half, width_half, height_half = half

        local_footprint = np.array(
            [
                [-length_half, -width_half],
                [length_half, -width_half],
                [length_half, width_half],
                [-length_half, width_half],
            ]
        )
        cos_h, sin_h = np.cos(self.heading_rad), np.sin(self.heading_rad)
        rotation = np.array([[cos_h, -sin_h], [sin_h, cos_h]])
        world_footprint = local_footprint @ rotation.T + self.center[:2]

        z_min = self.center[2] - height_half
        z_max = self.center[2] + height_half
        base = np.column_stack([world_footprint, np.full(4, z_min)])
        top = np.column_stack([world_footprint, np.full(4, z_max)])

        return np.vstack([base, top])


def extract_bbox_3d(building: Building) -> BoundingBox3D:
    """Extract a BoundingBox3D from one generated Building."""
    x_min, y_min, x_max, y_max = building.aabb
    height = building.height
    if building.label_extent is not None:
        x_min, y_min, x_max, y_max, height = building.label_extent
    length = x_max - x_min
    width = y_max - y_min

    center = np.array([(x_min + x_max) / 2.0, (y_min + y_max) / 2.0, height / 2.0])
    dimensions = np.array([length, width, height])

    return BoundingBox3D(object_id=building.building_id, center=center, dimensions=dimensions)


def extract_bboxes_3d(buildings: List[Building]) -> List[BoundingBox3D]:
    """Extract a BoundingBox3D for every building in a scenario."""
    return [extract_bbox_3d(building) for building in buildings]


def extract_bbox_3d_vehicle(vehicle: Vehicle, id_offset: int = 0) -> BoundingBox3D:
    """Extract a BoundingBox3D from one placed Vehicle.

    ``id_offset`` disambiguates ``vehicle.vehicle_id`` from other object
    kinds' own 0-based id counters (buildings, pedestrians) when combined
    into a single scenario's object_id space -- see
    ``dataset_generator.render_frame``, the only real caller.
    """
    # The box is the vehicle's real extent: centered on its box center (not the
    # mesh's placement point) and standing on the surface it is parked or driving
    # on, from its underside (``box_z_min``) up by its height.
    box_center = vehicle.box_center
    center = np.array(
        [
            box_center[0],
            box_center[1],
            vehicle.surface_z + vehicle.box_z_min + vehicle.height / 2.0,
        ]
    )
    dimensions = np.array([vehicle.length, vehicle.width, vehicle.height])
    category_id = VEHICLE_TYPE_TO_CATEGORY[vehicle.vehicle_type]

    return BoundingBox3D(
        object_id=vehicle.vehicle_id + id_offset,
        center=center,
        dimensions=dimensions,
        heading_rad=vehicle.heading_rad,
        category_id=category_id,
    )


def extract_bboxes_3d_vehicles(vehicles: List[Vehicle], id_offset: int = 0) -> List[BoundingBox3D]:
    """Extract a BoundingBox3D for every vehicle in a scenario."""
    return [extract_bbox_3d_vehicle(vehicle, id_offset) for vehicle in vehicles]


def extract_bbox_3d_pedestrian(pedestrian: Pedestrian, id_offset: int = 0) -> BoundingBox3D:
    """Extract a BoundingBox3D from one placed Pedestrian.

    ``pedestrian.depth`` (its forward-facing extent, matching
    ``heading_rad``'s own derivation) maps to ``dimensions``'s "length"
    axis, mirroring ``BoundingBox3D``'s own local-x-before-rotation
    convention.
    """
    forward, lateral = pedestrian.box_offset
    cos_h, sin_h = np.cos(pedestrian.heading_rad), np.sin(pedestrian.heading_rad)
    center = np.array(
        [
            pedestrian.center[0] + cos_h * forward - sin_h * lateral,
            pedestrian.center[1] + sin_h * forward + cos_h * lateral,
            pedestrian.surface_z + pedestrian.height / 2.0,
        ]
    )
    dimensions = np.array([pedestrian.depth, pedestrian.width, pedestrian.height])

    return BoundingBox3D(
        object_id=pedestrian.pedestrian_id + id_offset,
        center=center,
        dimensions=dimensions,
        heading_rad=pedestrian.heading_rad,
        category_id=PEDESTRIAN,
    )


def extract_bboxes_3d_pedestrians(
    pedestrians: List[Pedestrian], id_offset: int = 0
) -> List[BoundingBox3D]:
    """Extract a BoundingBox3D for every pedestrian in a scenario."""
    return [extract_bbox_3d_pedestrian(pedestrian, id_offset) for pedestrian in pedestrians]
