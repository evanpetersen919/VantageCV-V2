"""Lane markings: MUTCD dimensions, where lines start and stop, and that old seeds are unchanged."""

import math
from typing import Dict, List, Tuple

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural import lane_markings as lm
from src.procedural.crosswalks import CROSSWALK_PAINT_FAR_M, VEHICLE_STOP_SETBACK_M
from src.procedural.environment import TimeOfDay
from src.procedural.lane_topology import LANE_WIDTH_METERS
from src.procedural.mesh_factory import Mesh
from src.procedural.road_network import RoadEdge, RoadType
from src.utils.config_loader import load_scenario_config

TEMPLATE = "configs/scenario_templates/urban_dense_v14.yaml"
BOUNDS = (-150.0, -150.0, 150.0, 150.0)


def _road(lanes_forward: int, lanes_back: int, length: float = 200.0) -> Dict[int, RoadEdge]:
    """One straight physical road along +X from (0, 0) to (length, 0): its two directed edges."""
    forward = RoadEdge(
        0,
        0,
        1,
        RoadType.MINOR,
        np.array([[0.0, 0.0], [length, 0.0]]),
        length,
        lanes_forward,
        50,
        7.0,
        reverse_edge_id=1,
    )
    back = RoadEdge(
        1,
        1,
        0,
        RoadType.MINOR,
        np.array([[length, 0.0], [0.0, 0.0]]),
        length,
        lanes_back,
        50,
        7.0,
        reverse_edge_id=0,
    )
    return {0: forward, 1: back}


def _boxes(mesh: Mesh) -> List[Tuple[float, float, float, float]]:
    """(x_min, x_max, y_min, y_max) of every quad of a mesh."""
    quads = mesh.vertices.reshape(-1, 4, 3)
    return [(q[:, 0].min(), q[:, 0].max(), q[:, 1].min(), q[:, 1].max()) for q in quads]


def test_dash_pattern_is_ten_feet_on_thirty_feet_off() -> None:
    """MUTCD 3A.04: a broken line is a 10 ft dash and a 30 ft gap, starting with a dash."""
    dashes = lm.dash_ranges(0.0, 100.0)
    assert math.isclose(dashes[0][1] - dashes[0][0], 3.048, abs_tol=1e-6)
    assert math.isclose(dashes[1][0] - dashes[0][1], 9.144, abs_tol=1e-6)
    assert dashes[0][0] == 0.0 and all(b <= 100.0 for _, b in dashes)


def test_a_clipped_last_dash_is_dropped_when_too_short() -> None:
    """A dash shorter than the minimum at the end of a run is not painted."""
    pitch = lm.DASH_M + lm.DASH_GAP_M
    assert len(lm.dash_ranges(0.0, pitch + 0.2)) == 1
    assert len(lm.dash_ranges(0.0, pitch + 1.0)) == 2


def test_two_lane_two_way_road_has_a_double_yellow_and_stop_lines_only() -> None:
    """One lane each way: two yellow lines, no white lane line, one stop line per end."""
    edges = _road(1, 1)
    meshes = {m.material: m for m in lm.lane_marking_meshes(edges)}
    yellow = sorted(_boxes(meshes["paint_yellow"]), key=lambda box: box[2])
    assert len(yellow) == 2
    width = lm.LINE_WIDTH_NARROW_M
    assert all(math.isclose(box[3] - box[2], width, abs_tol=1e-6) for box in yellow)
    gap = yellow[1][2] - yellow[0][3]
    assert math.isclose(gap, lm.DOUBLE_LINE_GAP_FACTOR * width, abs_tol=1e-6)
    assert len(_boxes(meshes["paint_white"])) == 2  # the two stop lines


def test_four_lane_road_has_a_white_broken_line_in_each_direction() -> None:
    """Two lanes each way: a broken white line at one lane width on each side of the centre line."""
    edges = _road(2, 2)
    meshes = {m.material: m for m in lm.lane_marking_meshes(edges)}
    boxes = _boxes(meshes["paint_white"])
    lines = [
        b for b in boxes if b[3] - b[2] < 1.0
    ]  # the stop lines are as wide as the approach lanes
    centres = sorted({round((b[2] + b[3]) / 2.0, 3) for b in lines})
    assert centres == [-LANE_WIDTH_METERS, LANE_WIDTH_METERS]
    for box in lines:
        assert math.isclose(box[3] - box[2], lm.LINE_WIDTH_WIDE_M, abs_tol=1e-6)


def test_lines_stop_before_the_stop_line_and_stop_line_is_clear_of_the_crosswalk() -> None:
    """Painted runs end at each stop line, which sits 4 ft past the painted crosswalk."""
    edges = _road(2, 2, length=200.0)
    clearance = 2 * LANE_WIDTH_METERS
    meshes = {m.material: m for m in lm.lane_marking_meshes(edges)}
    near_edge = clearance + CROSSWALK_PAINT_FAR_M + lm.STOP_LINE_SETBACK_M
    stops = [b for b in _boxes(meshes["paint_white"]) if b[1] - b[0] < lm.STOP_LINE_WIDTH_M + 1e-6]
    assert len(stops) == 2
    assert math.isclose(min(b[0] for b in stops), near_edge, abs_tol=1e-6)
    far_edge = near_edge + lm.STOP_LINE_WIDTH_M
    for box in _boxes(meshes["paint_yellow"]):
        assert math.isclose(box[0], far_edge, abs_tol=1e-6)
        assert math.isclose(box[1], 200.0 - far_edge, abs_tol=1e-6)


def test_the_stop_line_is_close_to_the_intersection_and_the_queue_stops_behind_it() -> None:
    """The line is a few metres beyond the painted crosswalk; the queue's bumper is behind it."""
    assert (
        9.0 < lm.STOP_LINE_FROM_CLEARANCE_M < 10.5
    )  # was 15 m, beyond the whole crosswalk footprint
    outer_edge = lm.STOP_LINE_FROM_CLEARANCE_M + lm.STOP_LINE_WIDTH_M / 2.0
    assert VEHICLE_STOP_SETBACK_M > outer_edge
    assert VEHICLE_STOP_SETBACK_M - outer_edge < 1.0


def _stop_line_boxes(meshes: List[Mesh]) -> List[Tuple[float, float, float, float]]:
    """(x_min, y_min, x_max, y_max) of every stop-line quad (a 24 in strip across lanes)."""
    boxes = []
    for mesh in meshes:
        for q in mesh.vertices.reshape(-1, 4, 3):
            dx, dy = np.ptp(q[:, 0]), np.ptp(q[:, 1])
            if math.isclose(min(dx, dy), lm.STOP_LINE_WIDTH_M, abs_tol=0.02) and max(dx, dy) > 3.0:
                boxes.append((q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max()))
    return boxes


def test_no_queued_vehicle_sits_on_a_stop_line() -> None:
    """With markings on, every queued car clears every stop line (the first stops behind it).

    Cars driving through on green sit anywhere in their lane and may cross a line, as in traffic.
    """
    marked = load_scenario_config(TEMPLATE)
    checked = 0
    for seed in (80003, 80004, 80005):
        scenario = generate_scenario(seed, marked, BOUNDS, "s", time_of_day=TimeOfDay.DAY)
        stops = _stop_line_boxes(lm.lane_marking_meshes(scenario.edges))
        assert stops
        for vehicle in [v for v in scenario.vehicles if v.braking]:
            x0, y0, x1, y1 = vehicle.aabb
            for sx0, sy0, sx1, sy1 in stops:
                overlap = min(x1, sx1) - max(x0, sx0) > 0.05 and min(y1, sy1) - max(y0, sy0) > 0.05
                assert not overlap, (seed, vehicle.vehicle_id)
            checked += 1
    assert checked > 100  # queued cars over the three seeds


def test_a_road_too_short_for_a_crosswalk_gets_no_stop_line() -> None:
    """Crosswalks are skipped on short roads, so no stop line is painted there either."""
    edges = _road(1, 1, length=15.0)
    meshes = {m.material: m for m in lm.lane_marking_meshes(edges)}
    assert "paint_white" not in meshes


def test_paint_faces_up_and_sits_just_above_the_road() -> None:
    """Every triangle's normal points up and every vertex is at the paint height."""
    edges = _road(2, 2)
    for mesh in lm.lane_marking_meshes(edges):
        vertices, triangles = mesh.vertices, mesh.triangles.reshape(-1, 3)
        normals = np.cross(
            vertices[triangles[:, 1]] - vertices[triangles[:, 0]],
            vertices[triangles[:, 2]] - vertices[triangles[:, 0]],
        )
        assert (normals[:, 2] > 0).all()
        assert np.allclose(vertices[:, 2], lm.PAINT_Z_M)


def test_markings_are_off_by_default_and_the_template_turns_them_on() -> None:
    """Old templates give the same meshes as before; v14 adds paint and moves the queues."""
    base = load_scenario_config("configs/scenario_templates/urban_dense_v13r.yaml")
    marked = load_scenario_config(TEMPLATE)
    assert base.lane_markings is False and marked.lane_markings is True
    plain = generate_scenario(80003, base, BOUNDS, "a", time_of_day=TimeOfDay.DAY)
    painted = generate_scenario(80003, marked, BOUNDS, "a", time_of_day=TimeOfDay.DAY)
    extra = len(painted.meshes) - len(plain.meshes)
    assert extra in (1, 2) and all(m.material.startswith("paint") for m in painted.meshes[-extra:])
    assert [len(m.vertices) for m in plain.meshes] == [
        len(m.vertices) for m in painted.meshes[: len(plain.meshes)]
    ]
    assert len(plain.vehicles) > 0 and len(painted.vehicles) > 0


def test_summary_reports_area_per_material() -> None:
    """The painted area of a 200 m two-lane road: two yellow lines of 4 in plus the stop lines."""
    edges = _road(1, 1)
    area = lm.marking_summary(lm.lane_marking_meshes(edges))
    assert area["paint_yellow"] > 2 * lm.LINE_WIDTH_NARROW_M * 100.0
    assert area["paint_white"] > 0.0
