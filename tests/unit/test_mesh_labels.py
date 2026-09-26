"""Tests for tight 2D labels taken from projected render meshes."""

import numpy as np
import pytest

from src.export.coco_exporter import CocoFrame, export_coco
from src.ground_truth.bbox_2d import BoundingBox2D, project_bbox_3d_to_2d
from src.ground_truth.bbox_3d import extract_bbox_3d_vehicle
from src.ground_truth.mesh_labels import (
    project_vertices,
    refine_with_meshes,
    silhouette_polygon,
    tight_box_2d,
)
from src.orchestration.live_render import ue_camera
from src.procedural.actor_placement import Vehicle, vehicle_box
from src.procedural.vehicle_meshes import world_triangles
from src.sensors.camera_model import Camera

CAR_PATH = "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02"
WIDTH, HEIGHT = 1920, 1080


def _car(heading: float) -> Vehicle:
    """A sedan of the measured model at the origin."""
    length, width, height, offset_x, offset_y, z_min = vehicle_box(CAR_PATH, "sedan")
    return Vehicle(
        box_z_min=z_min,
        box_offset=(offset_x, offset_y),
        heading_rad=heading,
        center=np.zeros(2),
        asset_path=CAR_PATH,
        vehicle_type="sedan",
        vehicle_id=0,
        height=height,
        width=width,
        length=length,
    )


def _oblique_camera() -> Camera:
    """A camera 12 m from the origin at sensor height, 30 degrees round, looking at it."""
    angle = np.radians(30.0)
    position = np.array([12.0 * np.cos(angle), 12.0 * np.sin(angle), 1.6])
    return ue_camera(position, np.array([0.0, 0.0, 0.8]), WIDTH, HEIGHT)


def _corner_box(camera: Camera, car: Vehicle) -> BoundingBox2D:
    """The box-derived 2D label of ``car``."""
    box = project_bbox_3d_to_2d(camera, extract_bbox_3d_vehicle(car))
    assert box is not None
    return box


def test_mesh_box_is_tighter_than_the_corner_box_for_an_oblique_car() -> None:
    """The extent of the projected mesh is smaller than the hull of the 3D box's corners."""
    camera = _oblique_camera()
    car = _car(np.radians(20.0))
    corner = _corner_box(camera, car)
    soup = world_triangles(car)
    assert soup is not None
    boxes, silhouettes = refine_with_meshes(camera, [corner], {0: soup})
    assert len(boxes) == 1
    assert boxes[0].area < corner.area * 0.9
    assert boxes[0].area > corner.area * 0.5
    assert 0 in silhouettes and len(silhouettes[0]) >= 3


def test_objects_without_a_mesh_keep_their_box() -> None:
    """Only objects that have a mesh are refined."""
    camera = _oblique_camera()
    corner = _corner_box(camera, _car(0.0))
    boxes, silhouettes = refine_with_meshes(camera, [corner], {})
    assert boxes == [corner]
    assert not silhouettes


def test_mesh_entirely_behind_the_camera_keeps_the_box_label() -> None:
    """A mesh wholly behind the camera cannot be projected, so it keeps its label."""
    camera = ue_camera(np.array([0.0, 0.0, 1.5]), np.array([10.0, 0.0, 1.5]), WIDTH, HEIGHT)
    triangles = np.array([[[-5.0, 0.0, 1.0], [-6.0, 1.0, 1.0], [-5.0, -1.0, 2.0]]])
    assert project_vertices(camera, triangles) is None
    box = BoundingBox2D(3, 100.0, 100.0, 200.0, 200.0, 1.0)
    boxes, _ = refine_with_meshes(camera, [box], {3: triangles})
    assert boxes == [box]


def test_mesh_crossing_the_near_plane_is_cut_there() -> None:
    """A triangle from behind the camera to in front of it projects to its visible part."""
    camera = ue_camera(np.array([0.0, 0.0, 1.5]), np.array([10.0, 0.0, 1.5]), WIDTH, HEIGHT)
    triangles = np.array([[[-2.0, 0.0, 0.5], [10.0, 1.0, 2.5], [10.0, -1.0, 2.5]]])
    pixels = project_vertices(camera, triangles)
    assert pixels is not None
    assert np.isfinite(pixels).all()
    assert len(pixels) == 4  # two vertices in front plus two edge crossings of the near plane
    box = BoundingBox2D(3, 0.0, 0.0, 10.0, 10.0, 1.0)
    boxes, _ = refine_with_meshes(camera, [box], {3: triangles})
    assert len(boxes) == 1 and boxes[0].x_max > boxes[0].x_min


def test_mesh_entirely_outside_the_image_is_dropped() -> None:
    """A mesh that projects wholly outside the frame has no label."""
    camera = ue_camera(np.array([0.0, 0.0, 1.5]), np.array([10.0, 0.0, 1.5]), WIDTH, HEIGHT)
    far_left = np.array([[[10.0, 60.0, 1.0], [10.0, 61.0, 1.0], [10.0, 60.5, 2.0]]])
    box = BoundingBox2D(4, 100.0, 100.0, 200.0, 200.0, 1.0)
    boxes, silhouettes = refine_with_meshes(camera, [box], {4: far_left})
    assert not boxes
    assert not silhouettes


def test_tight_box_is_clipped_to_the_image() -> None:
    """A mesh hanging off the image edge is clipped to it."""
    camera = ue_camera(np.array([0.0, 0.0, 1.5]), np.array([10.0, 0.0, 1.5]), WIDTH, HEIGHT)
    box = BoundingBox2D(1, 0.0, 0.0, 10.0, 10.0, 1.0)
    pixels = np.array([[-50.0, 100.0], [300.0, 400.0], [200.0, 2000.0]])
    clipped = tight_box_2d(box, pixels, camera)
    assert clipped is not None
    assert clipped.x_min == 0.0 and clipped.y_max == HEIGHT
    assert clipped.x_max == pytest.approx(300.0)


def test_silhouette_of_a_square_is_its_four_corners() -> None:
    """The convex hull of a point cloud is its outline."""
    points = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [5.0, 5.0]])
    hull = silhouette_polygon(points)
    assert hull is not None and len(hull) == 4


def test_exporter_uses_the_mesh_silhouette_when_given() -> None:
    """A frame's silhouette replaces the box-corner hull in the COCO segmentation."""
    camera = _oblique_camera()
    car = _car(0.0)
    box_3d = extract_bbox_3d_vehicle(car)
    box_2d = _corner_box(camera, car)
    polygon = np.array([[10.0, 10.0], [50.0, 10.0], [50.0, 40.0]])
    frame = CocoFrame(
        image_id=0,
        file_name="x.png",
        camera=camera,
        bboxes_2d=[box_2d],
        bboxes_3d_by_id={0: box_3d},
        silhouettes_by_id={0: polygon},
    )
    annotation = export_coco([frame])["annotations"][0]
    assert annotation["segmentation"] == [polygon.flatten().tolist()]
