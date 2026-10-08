"""KITTI 3D boxes: hand-built cases, the devkit's own corner formula as an independent round trip,
and the
text formats."""

# pylint: disable=missing-function-docstring,duplicate-code

import math

import numpy as np
import pytest

from src.export.box3d_formats import (
    camera_box,
    kitti_calibration,
    kitti_label_line,
    occluded_level,
    projection_matrix,
)
from src.export.coco_exporter import export_coco
from src.ground_truth.bbox_2d import project_bboxes_3d_to_2d
from src.ground_truth.bbox_3d import BoundingBox3D
from src.orchestration.dataset_generator import generate_scenario, render_frame
from src.orchestration.live_render import ue_camera
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.utils.config_loader import load_scenario_config

WIDTH, HEIGHT = 1280, 720


def _level_camera() -> Camera:
    """At 1.5 m, looking along world +y: camera x is world +x (right), camera z is world +y."""
    extrinsics = CameraExtrinsics.looking_at(np.array([0.0, 0.0, 1.5]), np.array([0.0, 10.0, 1.5]))
    return Camera(CameraIntrinsics.from_fov(90.0, WIDTH, HEIGHT), extrinsics)


def _car(x: float, y: float, heading: float) -> BoundingBox3D:
    return BoundingBox3D(
        object_id=1,
        center=np.array([x, y, 0.75]),
        dimensions=np.array([4.0, 1.8, 1.5]),  # length, width, height
        heading_rad=heading,
    )


def key(a):  # type: ignore[no-untyped-def]
    """Corner rows in a canonical order, to compare two sets of points."""
    return a[np.lexsort((a[:, 1], a[:, 0]))]


def _devkit_corners(location, hwl, rotation_y):  # type: ignore[no-untyped-def]
    """The KITTI devkit's own corner construction (``compute_box_3d``), written separately here."""
    h, w, l = hwl
    c, s = math.cos(rotation_y), math.sin(rotation_y)
    rotation = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    x = [l / 2, l / 2, -l / 2, -l / 2, l / 2, l / 2, -l / 2, -l / 2]
    y = [0, 0, 0, 0, -h, -h, -h, -h]
    z = [w / 2, -w / 2, -w / 2, w / 2, w / 2, -w / 2, -w / 2, w / 2]
    return rotation @ np.array([x, y, z]) + np.array(location).reshape(3, 1)


def test_a_car_driving_away_along_the_line_of_sight_has_rotation_y_minus_half_pi() -> None:
    box = camera_box(_level_camera(), _car(0.0, 20.0, math.pi / 2.0))
    assert box.rotation_y == pytest.approx(-math.pi / 2.0)
    assert box.alpha == pytest.approx(-math.pi / 2.0)  # straight ahead: no viewing angle
    assert box.location[2] == pytest.approx(20.0)
    assert box.location[1] == pytest.approx(
        1.5
    )  # the bottom is 1.5 m below the camera (y points down)
    assert box.dimensions_hwl == pytest.approx((1.5, 1.8, 4.0))


def test_the_opposite_heading_flips_rotation_y_by_pi() -> None:
    camera = _level_camera()
    away = camera_box(camera, _car(0.0, 20.0, math.pi / 2.0)).rotation_y
    towards = camera_box(camera, _car(0.0, 20.0, -math.pi / 2.0)).rotation_y
    assert abs(towards - away) == pytest.approx(math.pi)


def test_alpha_is_rotation_y_minus_the_viewing_angle() -> None:
    box = camera_box(_level_camera(), _car(10.0, 20.0, math.pi / 2.0))
    viewing = math.atan2(10.0, 20.0)
    assert box.alpha == pytest.approx(box.rotation_y - viewing)
    left = camera_box(_level_camera(), _car(-10.0, 20.0, math.pi / 2.0))
    assert left.alpha == pytest.approx(left.rotation_y + viewing)


@pytest.mark.parametrize("heading", [0.0, 0.7, math.pi / 2.0, 2.5, -1.2])
@pytest.mark.parametrize("position", [(0.0, 20.0), (8.0, 15.0), (-6.0, 30.0)])
def test_devkit_corners_projected_with_p_equal_the_original_corners_projected(
    heading: float, position: tuple
) -> None:
    camera = _level_camera()
    box3d = _car(position[0], position[1], heading)
    box = camera_box(camera, box3d)
    rebuilt = _devkit_corners(box.location, box.dimensions_hwl, box.rotation_y)
    homogeneous = projection_matrix(camera) @ np.vstack([rebuilt, np.ones(8)])
    rebuilt_pixels = (homogeneous[:2] / homogeneous[2]).T
    original = np.array([camera.project(corner)[0] for corner in box3d.corners()])
    assert key(rebuilt_pixels) == pytest.approx(key(original), abs=1e-6)


def test_every_exported_object_of_generated_scenarios_round_trips() -> None:
    """A camera tilted down about 4 degrees: the level frame and P keep the round trip exact."""
    config = load_scenario_config("configs/scenario_templates/urban_dense_v8a.yaml")
    checked = 0
    for seed in (70000, 70001, 70002):
        scenario = generate_scenario(seed, config, (-150.0, -150.0, 150.0, 150.0), f"t{seed}")
        centre = np.asarray(scenario.vehicles[0].box_center, dtype=np.float64)
        camera = ue_camera(
            np.array([centre[0] - 6.0, centre[1] - 6.0, 1.6]),
            np.array([centre[0], centre[1], 1.0]),
            WIDTH,
            HEIGHT,
        )
        frame = render_frame(scenario, camera, 1, "x.png")
        for annotation in export_coco([frame])["annotations"]:
            if "box3d" not in annotation:
                continue
            b = annotation["box3d"]
            corners = _devkit_corners(b["location"], b["dimensions_hwl"], b["rotation_y"])
            homogeneous = projection_matrix(camera) @ np.vstack([corners, np.ones(8)])
            pixels = (homogeneous[:2] / homogeneous[2]).T
            source = frame.bboxes_3d_by_id[
                next(
                    o
                    for o, v in frame.bboxes_3d_by_id.items()
                    if camera_box(camera, v).location == pytest.approx(tuple(b["location"]))
                )
            ]
            expected = np.array(
                [camera.project(c)[0] for c in source.corners() if camera.project(c)[0] is not None]
            )
            if len(expected) == 8:
                assert key(pixels) == pytest.approx(key(expected), abs=1e-5)
                checked += 1
    assert checked > 20


def test_label_line_has_15_fields_and_16_with_a_score() -> None:
    box = camera_box(_level_camera(), _car(2.0, 18.0, 0.3))
    line = kitti_label_line("Car", 0.1, 0.95, (100.0, 200.0, 50.0, 40.0), box)
    parts = line.split()
    assert len(parts) == 15 and parts[0] == "Car"
    assert [float(p) for p in parts[1:]]  # everything after the type is numeric
    assert parts[2] == "0"  # visibility 0.95 -> not occluded
    assert (float(parts[6]), float(parts[7])) == (150.0, 240.0)  # x2, y2 from x, y, width, height
    assert len(kitti_label_line("Car", 0.0, 1.0, (0, 0, 1, 1), box, score=0.9).split()) == 16


def test_occlusion_levels() -> None:
    assert [occluded_level(v) for v in (1.0, 0.91, 0.9, 0.7, 0.6, 0.2)] == [0, 0, 1, 1, 2, 2]


def test_calibration_has_the_seven_matrices_with_the_right_sizes() -> None:
    lines = kitti_calibration(_level_camera()).strip().split("\n")
    names = [line.split(":")[0] for line in lines]
    assert names == ["P0", "P1", "P2", "P3", "R0_rect", "Tr_velo_to_cam", "Tr_imu_to_velo"]
    sizes = [len(line.split(":")[1].split()) for line in lines]
    assert sizes == [12, 12, 12, 12, 9, 12, 12]
    p2 = np.array(lines[2].split(":")[1].split(), dtype=float).reshape(3, 4)
    assert p2[0, 0] == pytest.approx(WIDTH / 2.0)  # a 90 degree field of view
    assert p2[:, 3] == pytest.approx(0.0)


def test_coco_annotations_carry_the_camera_box_and_old_keys_stay() -> None:
    camera = _level_camera()
    box3d = _car(0.0, 20.0, math.pi / 2.0)
    box2d = project_bboxes_3d_to_2d(camera, [box3d])
    from src.export.coco_exporter import CocoFrame  # pylint: disable=import-outside-toplevel

    result = export_coco([CocoFrame(1, "a.png", camera, box2d, {box3d.object_id: box3d})])
    annotation = result["annotations"][0]
    assert {"id", "image_id", "category_id", "bbox", "area", "iscrowd", "segmentation"} <= set(
        annotation
    )
    assert annotation["box3d"]["rotation_y"] == pytest.approx(-math.pi / 2.0)


@pytest.mark.parametrize("pitch_deg", [3.0, 8.0, 15.0])
def test_a_pitched_camera_stays_exact_and_p_carries_the_rotation(pitch_deg: float) -> None:
    height = 1.6
    target = np.array([0.0, 20.0, height - 20.0 * math.tan(math.radians(pitch_deg))])
    extrinsics = CameraExtrinsics.looking_at(np.array([0.0, 0.0, height]), target)
    camera = Camera(CameraIntrinsics.from_fov(106.0, 1920, 1080), extrinsics)
    box3d = _car(1.0, 12.0, 0.8)
    box = camera_box(camera, box3d)
    corners = _devkit_corners(box.location, box.dimensions_hwl, box.rotation_y)
    homogeneous = projection_matrix(camera) @ np.vstack([corners, np.ones(8)])
    pixels = (homogeneous[:2] / homogeneous[2]).T
    original = np.array([camera.project(c)[0] for c in box3d.corners()])
    assert key(pixels) == pytest.approx(key(original), abs=1e-6)
    assert not np.allclose(
        projection_matrix(camera)[:, :3], camera.intrinsics.get_intrinsic_matrix()
    )
    assert box.location[1] > 0.0  # the bottom of the box is below the camera in the level frame
