"""Tests for the dumped vehicle render meshes and mesh-based occlusion."""

import numpy as np
import pytest

from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.categories import SEDAN
from src.ground_truth.occlusion import visible_fraction
from src.procedural.actor_placement import Vehicle, vehicle_box
from src.procedural.vehicle_bounds import VEHICLE_MODEL_BOUNDS
from src.procedural.vehicle_meshes import model_folder, model_mesh, world_triangles
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics

CAR_PATH = "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02"


def _vehicle(heading: float = 0.0, x: float = 0.0, y: float = 0.0) -> Vehicle:
    """A sedan of the measured model at (x, y)."""
    length, width, height, offset_x, offset_y, z_min = vehicle_box(CAR_PATH, "sedan")
    extents = {"length": length, "width": width, "height": height}
    return Vehicle(
        0,
        "sedan",
        CAR_PATH,
        np.array([x, y]),
        heading,
        box_z_min=z_min,
        box_offset=(offset_x, offset_y),
        **extents,
    )


def test_every_measured_model_has_a_mesh() -> None:
    """The mesh file covers every model in the bounds table."""
    for folder in VEHICLE_MODEL_BOUNDS:
        assert model_mesh(folder) is not None, folder


def test_mesh_length_and_ground_contact_match_the_measured_box() -> None:
    """The mesh agrees with the measured bounds along the vehicle.

    Doors and interior add width, and coarse detail levels drop small roof fittings
    (the police car's light bar), hence the height tolerance.
    """
    for folder, (length, _, height, center_x, _, z_min) in VEHICLE_MODEL_BOUNDS.items():
        vertices, _ = model_mesh(folder)  # type: ignore[misc]
        low, high = vertices.min(axis=0), vertices.max(axis=0)
        assert high[0] - low[0] == pytest.approx(length, abs=0.3), folder
        assert (high[0] + low[0]) / 2.0 == pytest.approx(center_x, abs=0.3), folder
        assert low[2] == pytest.approx(z_min, abs=0.05), folder
        assert high[2] - low[2] >= height - 0.2, folder


def test_unknown_model_has_no_mesh() -> None:
    """A model that was never dumped reports None."""
    assert model_mesh("vehNothing_vehicle99") is None
    assert model_folder(CAR_PATH) == "vehCar_vehicle02"


def test_world_triangles_apply_heading_and_position() -> None:
    """A quarter turn swaps the extents; the placement point translates the mesh."""
    straight = world_triangles(_vehicle(0.0, 10.0, -4.0))
    turned = world_triangles(_vehicle(np.pi / 2, 10.0, -4.0))
    assert straight is not None and turned is not None
    straight_points, turned_points = straight.reshape(-1, 3), turned.reshape(-1, 3)
    straight_size = straight_points.max(axis=0) - straight_points.min(axis=0)
    turned_size = turned_points.max(axis=0) - turned_points.min(axis=0)
    assert straight_size[0] == pytest.approx(turned_size[1], abs=0.02)
    assert straight_size[1] == pytest.approx(turned_size[0], abs=0.02)
    assert straight_points[:, 0].mean() == pytest.approx(10.0, abs=0.5)
    assert straight_points[:, 1].mean() == pytest.approx(-4.0, abs=0.5)


def _camera() -> Camera:
    """Camera at the origin, 2 m up, looking along +x."""
    return Camera(
        CameraIntrinsics.from_fov(90.0, 1280, 720),
        CameraExtrinsics.looking_at(np.array([0.0, 0.0, 2.0]), np.array([50.0, 0.0, 2.0])),
    )


def test_occluder_mesh_with_a_gap_beats_its_own_box() -> None:
    """A wall mesh covering half of its box lets a car behind the other half show through."""
    camera = _camera()
    car = BoundingBox3D(
        1, np.array([30.0, 0.0, 0.75]), np.array([4.5, 1.9, 1.5]), category_id=SEDAN
    )
    wall_box = BoundingBox3D(
        2, np.array([15.0, 0.0, 2.0]), np.array([0.4, 12.0, 4.0]), category_id=SEDAN
    )
    # Two triangles forming a vertical plate over y in [0, 6] only.
    plate = np.array(
        [
            [[15.0, 0.0, 0.0], [15.0, 6.0, 0.0], [15.0, 6.0, 4.0]],
            [[15.0, 0.0, 0.0], [15.0, 6.0, 4.0], [15.0, 0.0, 4.0]],
        ]
    )
    with_box = visible_fraction(camera, car, [car, wall_box])
    with_mesh = visible_fraction(camera, car, [car, wall_box], {2: plate})
    assert with_box == 0.0
    assert 0.3 < with_mesh < 0.7
