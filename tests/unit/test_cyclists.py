"""Unit tests for cyclist placement (``cyclists.py``)."""

import math

import numpy as np
import pytest

from src.ground_truth.bbox_3d import extract_bboxes_3d_cyclists
from src.ground_truth.categories import BICYCLE, PROFILES, RIDER
from src.ground_truth.semantic_classes import asset_class
from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import object_asset_indices, serialize_scenario
from src.procedural import cyclists as cy
from src.procedural.actor_placement import Vehicle
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_network import RoadNetworkGenerator
from src.utils.config_loader import load_scenario_config
from tests.conftest import straight_road_lanes_and_edges

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
TEMPLATE = "configs/scenario_templates/urban_dense_v17.yaml"


def _network(seed: int = 80003):
    config = load_scenario_config(TEMPLATE)
    nodes, edges = RoadNetworkGenerator(seed, config).generate(BOUNDS)
    return LaneTopologyGenerator().generate(nodes, edges), edges


def _vehicle(x: float, y: float, heading: float = 0.0) -> Vehicle:
    return Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path="/Game/Vehicle/x",
        center=np.array([x, y]),
        heading_rad=heading,
        length=4.6,
        width=1.8,
        height=1.5,
    )


def test_assets_follow_the_baked_naming() -> None:
    """A cyclist is a rider mesh, a bicycle frame and 12 other parts at one crank angle."""
    c = cy.Cyclist(0, np.array([0.0, 0.0]), 0.0, "Male_Adult_01", 90)
    assert c.rider_asset.endswith("rider_Male_Adult_01_c90")
    assert c.bike_asset.endswith("bike_real_c90_frame")
    assert len(c.bike_part_paths) == 12
    assert all("_c90_" in path for path in c.bike_part_paths)


def test_no_cyclists_on_a_road_too_short_for_the_margins() -> None:
    """A run shorter than twice the end margin gets none."""
    lanes, edges = straight_road_lanes_and_edges(2.0 * cy.END_MARGIN_M - 1.0)
    assert not cy.generate_cyclists(lanes, edges, [], 1, run_probability=1.0)


def test_placement_is_deterministic_and_seed_dependent() -> None:
    """The same seed gives the same cyclists; another seed another set."""
    lanes, edges = _network()
    first = cy.generate_cyclists(lanes, edges, [], 5)
    again = cy.generate_cyclists(lanes, edges, [], 5)
    other = cy.generate_cyclists(lanes, edges, [], 6)
    assert len(first) > 5
    assert [(tuple(c.center), c.avatar, c.crank_deg) for c in first] == [
        (tuple(c.center), c.avatar, c.crank_deg) for c in again
    ]
    assert [tuple(c.center) for c in first] != [tuple(c.center) for c in other]


def test_cyclists_ride_in_the_direction_of_travel_inside_the_road() -> None:
    """Each cyclist's heading is an edge's direction, and its centre is on the road, 0.75 m from the
    curb line of that edge's outer lane."""
    lanes, edges = _network()
    riders = cy.generate_cyclists(lanes, edges, [], 5, run_probability=1.0)
    assert riders
    directions = {}
    for edge in edges.values():
        d = edge.centerline[-1] - edge.centerline[0]
        directions[edge.edge_id] = math.atan2(d[1], d[0])
    for rider in riders:
        assert any(
            abs(math.remainder(rider.heading_rad - angle, 2 * math.pi)) < 1e-6
            for angle in directions.values()
        )
        on_a_lane = False
        for lane in lanes.values():
            both = np.vstack([np.asarray(lane.left_boundary), np.asarray(lane.right_boundary)])
            lo, hi = both.min(axis=0), both.max(axis=0)
            if (rider.center >= lo).all() and (rider.center <= hi).all():
                on_a_lane = True
                break
        assert on_a_lane


def test_cyclists_keep_clear_of_vehicles_and_each_other() -> None:
    """With vehicles on would-be spots, no cyclist box touches a vehicle box; none overlap."""
    lanes, edges = _network()
    base = cy.generate_cyclists(lanes, edges, [], 5, run_probability=1.0)
    vehicles = [_vehicle(float(c.center[0]), float(c.center[1])) for c in base[:10]]
    riders = cy.generate_cyclists(lanes, edges, vehicles, 5, run_probability=1.0)
    for rider in riders:
        for vehicle in vehicles:
            assert not cy._overlaps(  # pylint: disable=protected-access
                rider.footprint_aabb(), vehicle.aabb, 0.0
            )
    boxes = [r.footprint_aabb() for r in riders]
    for i, first in enumerate(boxes):
        for second in boxes[i + 1 :]:
            assert not cy._overlaps(first, second, 0.0)  # pylint: disable=protected-access


@pytest.mark.parametrize("heading", [0.0, math.pi / 2, math.pi, -math.pi / 2])
def test_world_box_puts_the_length_along_the_heading(heading: float) -> None:
    """The bicycle's long axis is along the heading; its centre is forward of the origin."""
    c = cy.Cyclist(0, np.array([10.0, 20.0]), heading, "Male_Adult_01", 0)
    centre, length, width, z0, z1 = c.world_box(cy.BIKE_BOUNDS)
    assert length == pytest.approx(1.7620, abs=1e-3) and width == pytest.approx(0.66, abs=1e-3)
    forward = np.array([math.cos(heading), math.sin(heading)])
    assert float(np.dot(centre - c.center, forward)) == pytest.approx(
        (-0.7913 + 0.9707) / 2, abs=1e-3
    )
    assert z0 == 0.0 and z1 == pytest.approx(0.9542)


# ---------------------------------------------------------------- integration with the scenario


def _scenario(seed: int = 80003, template: str = "configs/scenario_templates/urban_dense_v18.yaml"):
    return generate_scenario(seed, load_scenario_config(template), BOUNDS, "s")


def test_off_by_default_and_on_in_the_v18_template() -> None:
    """Earlier templates place no cyclist; v18 does, and nothing else about the scene changes."""
    assert load_scenario_config(TEMPLATE).cyclists is False
    assert load_scenario_config("configs/scenario_templates/urban_dense_v18.yaml").cyclists is True
    plain = _scenario(template=TEMPLATE)
    with_cyclists = _scenario()
    assert not plain.cyclists and with_cyclists.cyclists
    assert [tuple(v.center) for v in plain.vehicles] == [
        tuple(v.center) for v in with_cyclists.vehicles
    ]
    assert len(plain.pedestrians) == len(with_cyclists.pedestrians)


def test_payload_has_a_rider_and_a_bicycle_per_cyclist_with_unique_ids() -> None:
    """Two entries per cyclist (rider mesh, bicycle frame with 12 parts) at one transform."""

    scenario = _scenario()
    payload = serialize_scenario(scenario, None)
    riders = [a for a in payload["assets"] if "/Riders/Spike/rider_" in a["asset_path"]]
    bikes = [a for a in payload["assets"] if "/Riders/Spike/bike_" in a["asset_path"]]
    assert len(riders) == len(bikes) == len(scenario.cyclists)
    assert all(len(b["part_paths"]) == 12 for b in bikes)
    assert [r["position"] for r in riders] == [b["position"] for b in bikes]
    ids = [a["id"] for a in riders + bikes]
    assert len(ids) == len(set(ids))  # the cyclists' own entries never share an id


def test_boxes_labels_and_object_members_for_cyclists() -> None:
    """Each cyclist yields a rider box and a bicycle box with their categories, and the exact-label
    members point at the matching assets."""
    scenario = _scenario()
    boxes = extract_bboxes_3d_cyclists(scenario.cyclists, id_offset=1000)
    assert len(boxes) == 2 * len(scenario.cyclists)
    assert [b.category_id for b in boxes[:2]] == [RIDER, BICYCLE]
    assert [b.object_id for b in boxes[:4]] == [1000, 1001, 1002, 1003]
    for box in boxes:
        assert (box.dimensions > 0).all() and box.center[2] > 0
    payload = serialize_scenario(scenario, None)
    members = object_asset_indices(scenario, payload)
    base = len(scenario.buildings) + len(scenario.vehicles) + len(scenario.pedestrians)
    first = scenario.cyclists[0]
    rider_index = members[base + 2 * first.cyclist_id][0]
    bike_index = members[base + 2 * first.cyclist_id + 1][0]
    assert payload["assets"][rider_index]["asset_path"] == first.rider_asset
    assert payload["assets"][bike_index]["asset_path"] == first.bike_asset


def test_class_map_labels_rider_and_bicycle_and_the_riders_profile_exports_them() -> None:
    """Cityscapes ids 25 and 33 for the meshes, and the riders profile maps the two categories."""
    c = cy.Cyclist(0, np.array([0.0, 0.0]), 0.0, "Male_Adult_01", 0)
    assert asset_class(c.rider_asset) == 25
    assert asset_class(c.bike_asset) == 33
    assert all(asset_class(p) == 33 for p in c.bike_part_paths)
    mapping = PROFILES["riders"].mapping
    assert mapping[RIDER] == 10 and mapping[BICYCLE] == 2
    assert {name for _, name in PROFILES["riders"].categories} >= {"rider", "bike", "person"}
    assert RIDER not in PROFILES["fine"].mapping and RIDER not in PROFILES["coco"].mapping
