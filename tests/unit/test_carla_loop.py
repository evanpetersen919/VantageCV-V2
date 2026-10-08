"""The pure logic of the CARLA harness: routes, collisions, summaries, projection, depth, IoU.

These need the CARLA Python package and the ``agents`` folder of the CARLA download, not a running
server, so they are skipped where CARLA is not installed (for example on CI).
"""

# pylint: disable=missing-function-docstring,duplicate-code,wrong-import-position

import math
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("carla")
if not (
    Path(os.environ.get("CARLA_ROOT", r"F:\CARLA_0.9.16")) / "PythonAPI" / "carla" / "agents"
).exists():
    pytest.skip("the CARLA download (agents folder) is not available", allow_module_level=True)

from carla_loop.compare import routes_with_collision
from carla_loop.harness import debounce, pick_route, summarise
from carla_loop.perception import decode_depth, intrinsics, iou, project_box
from carla_loop.run_driving import parse_seeds


def test_pick_route_is_deterministic_and_respects_the_distance_window() -> None:
    rng = np.random.default_rng(0)
    coordinates = [tuple(map(float, c)) for c in rng.uniform(0, 600, size=(200, 3))]
    points = []
    for p in coordinates:
        located = SimpleNamespace(p=p)
        located.location = located  # distance() below reads .p of the other point
        located.distance = lambda other, p=p: math.dist(p, other.p)
        points.append(located)
    first = pick_route(points, seed=3, min_m=150.0, max_m=450.0)
    assert first == pick_route(points, seed=3, min_m=150.0, max_m=450.0)
    start, goal = first
    assert start != goal
    assert 150.0 <= math.dist(coordinates[start], coordinates[goal]) <= 450.0


def test_pick_route_raises_when_no_pair_fits() -> None:
    located = []
    for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)):
        item = SimpleNamespace(p=p)
        item.location = item
        item.distance = lambda other, p=p: math.dist(p, other.p)
        located.append(item)
    with pytest.raises(RuntimeError):
        pick_route(located, seed=0, min_m=150.0, max_m=450.0)


def test_debounce_counts_one_crash_per_contact_and_a_later_one_again() -> None:
    events = [
        (1.0, "vehicle.a"),
        (1.05, "vehicle.a"),
        (1.5, "vehicle.a"),
        (3.0, "vehicle.a"),
        (3.1, "vehicle.b"),
    ]
    kept = debounce(events)
    assert [(k["t"], k["with"]) for k in kept] == [
        (1.0, "vehicle.a"),
        (3.0, "vehicle.a"),
        (3.1, "vehicle.b"),
    ]


def test_summarise_counts_outcomes_and_collisions_per_kilometre() -> None:
    rows = [
        {
            "outcome": "reached",
            "route_completion": 1.0,
            "distance_m": 1000.0,
            "collisions": [{"t": 1}],
            "lane_invasions": 2,
            "hard_brake_events": 10,
        },
        {
            "outcome": "stuck",
            "route_completion": 0.5,
            "distance_m": 1000.0,
            "collisions": [],
            "lane_invasions": 0,
            "hard_brake_events": 4,
        },
    ]
    summary = summarise(rows)
    assert summary["episodes"] == 2 and summary["reached"] == 1 and summary["stuck"] == 1
    assert summary["mean_completion"] == pytest.approx(0.75)
    assert summary["collisions"] == 1 and summary["collisions_per_km"] == pytest.approx(0.5)
    assert summary["hard_brake_events_per_km"] == pytest.approx(7.0)
    assert summarise([])["collisions_per_km"] is None


def test_routes_with_collision_counts_per_arm() -> None:
    rows = [
        {"arm": "a", "collisions": [1]},
        {"arm": "a", "collisions": []},
        {"arm": "b", "collisions": [1, 2]},
    ]
    assert routes_with_collision(rows, "a") == 1 and routes_with_collision(rows, "b") == 1


def test_parse_seeds_ranges_and_lists() -> None:
    assert parse_seeds("0-3") == [0, 1, 2, 3]
    assert parse_seeds("5") == [5]
    assert parse_seeds("0,2,7-8") == [0, 2, 7, 8]


def test_iou_of_boxes() -> None:
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1.0 / 3.0)


def test_intrinsics_of_a_ninety_degree_camera() -> None:
    k = intrinsics(1280, 720, 90.0)
    assert k[0, 0] == pytest.approx(640.0) and k[1, 1] == pytest.approx(640.0)
    assert (k[0, 2], k[1, 2]) == (640.0, 360.0)


def test_decode_depth_reads_carlas_24_bit_encoding() -> None:
    height, width = 2, 2
    pixels = np.zeros((height, width, 4), dtype=np.uint8)  # BGRA
    far = 256.0**3 - 1.0
    pixels[0, 0] = (255, 255, 255, 255)  # the maximum value: 1000 m
    pixels[0, 1] = (0, 0, 0, 255)  # 0 m
    value = 100.0 / 1000.0 * far  # 100 m
    pixels[1, 0, 2], pixels[1, 0, 1], pixels[1, 0, 0] = (
        int(value) % 256,
        (int(value) // 256) % 256,
        int(value) // 65536,
    )
    image = SimpleNamespace(raw_data=pixels.tobytes(), height=height, width=width)
    depth = decode_depth(image)
    assert depth[0, 0] == pytest.approx(1000.0, rel=1e-4)
    assert depth[0, 1] == 0.0
    assert depth[1, 0] == pytest.approx(100.0, rel=1e-3)


def test_project_box_in_front_of_and_behind_the_camera() -> None:
    k = intrinsics(1280, 720, 90.0)
    inverse = np.eye(4)  # camera at the origin looking along +x (CARLA: x forward, y right, z up)

    def vertex(x: float, y: float, z: float):  # type: ignore[no-untyped-def]
        return SimpleNamespace(x=x, y=y, z=z)

    front = [vertex(10.0, y, z) for y in (-1.0, 1.0) for z in (-1.0, 1.0)]
    box, depth = project_box(front, inverse, k, (1280, 720))  # type: ignore[misc]
    assert depth == pytest.approx(10.0)
    assert box[0] < 640 < box[2] and box[1] < 360 < box[3]
    assert (box[0] + box[2]) / 2 == pytest.approx(640.0, abs=0.5)
    behind = [vertex(-10.0, y, z) for y in (-1.0, 1.0) for z in (-1.0, 1.0)]
    assert project_box(behind, inverse, k, (1280, 720)) is None
