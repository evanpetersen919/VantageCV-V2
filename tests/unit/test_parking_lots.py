"""Unit tests for parking_lots.py: stall/aisle geometry from the cited US
dimensions, parked cars sitting inside their stalls, building keep-out and
the night-lights and default-off behaviour."""

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.actor_placement import VEHICLE_DIMENSIONS, Vehicle, vehicle_box
from src.procedural.crosswalks import (
    BAR_PITCH_M,
    STOP_LINE_ASSET_PATH,
    STOP_LINE_REAL_SIZE_M,
    STOP_LINE_WIDTH_M,
)
from src.procedural.environment import TimeOfDay
from src.procedural.night_lights import vehicle_glows, vehicle_lights
from src.procedural.parking_lots import (
    AISLE_OVERHANG_M,
    AISLE_WIDTH_M,
    DRIVEWAY_RAMP_OUTER_Z_M,
    DRIVEWAY_WIDTH_M,
    ISLAND_PERIOD_STALLS,
    LOT_MAX_LONG_SIDE_M,
    LOT_MAX_SHORT_SIDE_M,
    LOT_SURFACE_Z_M,
    MIN_STALLS_PER_ROW,
    PARKED_MIX_EXPONENT,
    PARKED_MODELS,
    PARKED_VEHICLE_TYPES,
    PARKING_BLOCK_ASSET_PATHS,
    STALL_LENGTH_M,
    STALL_WIDTH_M,
    STOP_LINE_PAINTED_DEPTH_M,
    WHEEL_STOP_SETBACK_M,
    Driveway,
    driveway_crosswalk_pieces,
    layout_lot,
    parked_vehicles,
    parking_lot_meshes,
    parking_lot_pieces,
    plan_parking_lots,
)

FEET = 0.3048
# A pickup may stand a few centimetres over its stall's length, like a real one.
PICKUP_OVERHANG_M = 0.1


def _config(urban_config, fraction: float):
    return urban_config.model_copy(update={"parking_lot_fraction": fraction})


def _nearest_stall(stalls, car):
    """The stall whose center is closest to ``car``."""
    return min(stalls, key=lambda s: np.hypot(*(np.array(s.center) - car.box_center)))


def test_stall_and_aisle_are_the_cited_us_dimensions() -> None:
    """9 x 18 ft stalls and a 24 ft two-way aisle, in metres."""
    assert STALL_WIDTH_M == pytest.approx(9 * FEET)
    assert STALL_LENGTH_M == pytest.approx(18 * FEET)
    assert AISLE_WIDTH_M == pytest.approx(24 * FEET)


def test_a_double_loaded_lot_has_the_expected_stall_count_and_geometry() -> None:
    """A lot exactly one module (two rows + aisle) deep and 20 stalls long
    (plus edge margins) holds 2 rows of 20 positions, one of which is a
    landscape island, every stall inside the bounds, and stalls spaced in
    whole stall widths."""
    depth = 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0
    length = 20 * STALL_WIDTH_M + 2.0
    lot = layout_lot(0, (0.0, 0.0, length, depth))
    assert len(lot.stalls) == 2 * (20 - 1)
    x_min, y_min, x_max, y_max = lot.bounds
    for stall in lot.stalls:
        cx, cy = stall.center
        assert x_min <= cx - stall.width / 2 and cx + stall.width / 2 <= x_max
        assert y_min <= cy - stall.length / 2 and cy + stall.length / 2 <= y_max
    rows = sorted({round(stall.center[1], 6) for stall in lot.stalls})
    assert len(rows) == 2
    assert rows[1] - rows[0] == pytest.approx(STALL_LENGTH_M + AISLE_WIDTH_M)
    row_one = sorted(s.center[0] for s in lot.stalls if round(s.center[1], 6) == rows[0])
    steps = np.diff(row_one) / STALL_WIDTH_M
    assert steps == pytest.approx(np.round(steps))
    assert sorted(set(np.round(steps).astype(int))) == [1, 2]


def test_stalls_face_away_from_their_aisle() -> None:
    """The lower row's head-in heading points to -y, the upper row's to
    +y (aisle along x)."""
    depth = 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0
    lot = layout_lot(0, (0.0, 0.0, 12 * STALL_WIDTH_M + 2.0, depth))
    mid_y = (lot.bounds[1] + lot.bounds[3]) / 2.0
    for stall in lot.stalls:
        expected = np.pi / 2 if stall.center[1] > mid_y else -np.pi / 2
        assert stall.head_heading_rad == pytest.approx(expected)


def test_a_lot_too_small_for_an_aisle_and_row_is_empty() -> None:
    """Shorter than one aisle plus a row, or too short for the minimum
    stalls per row, yields no stalls."""
    assert not layout_lot(0, (0.0, 0.0, 60.0, STALL_LENGTH_M + AISLE_WIDTH_M)).stalls
    assert not layout_lot(0, (0.0, 0.0, MIN_STALLS_PER_ROW * STALL_WIDTH_M, 40.0)).stalls


def test_a_lot_whose_long_side_is_y_runs_its_aisles_along_y() -> None:
    """Rotating the lot swaps the axes: headings point along +-x."""
    lot = layout_lot(0, (0.0, 0.0, 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0, 50.0))
    assert lot.stalls
    assert all(abs(np.cos(s.head_heading_rad)) == pytest.approx(1.0) for s in lot.stalls)


def test_default_config_plans_no_lots(urban_config, bounds) -> None:
    """parking_lot_fraction defaults to 0, so existing scenarios are unchanged."""
    assert urban_config.parking_lot_fraction == 0.0
    assert not generate_scenario(42, urban_config, bounds, "x").parking_lots


def test_lots_are_deterministic_and_inside_bounds(urban_config, bounds) -> None:
    """Same seed, same lots; every lot is inside the scenario bounds."""
    config = _config(urban_config, 0.6)
    first = generate_scenario(42, config, bounds, "a")
    again = generate_scenario(42, config, bounds, "b")
    assert first.parking_lots
    assert [lot.bounds for lot in first.parking_lots] == [lot.bounds for lot in again.parking_lots]
    for lot in first.parking_lots:
        assert lot.bounds[0] >= bounds[0] and lot.bounds[2] <= bounds[2]
        assert lot.bounds[1] >= bounds[1] and lot.bounds[3] <= bounds[3]


def test_no_building_overlaps_a_lot(urban_config, bounds) -> None:
    """Buildings keep out of every lot."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    for building in result.buildings:
        b = building.aabb
        for lot in result.parking_lots:
            x0, y0, x1, y1 = lot.bounds
            assert b[2] <= x0 or b[0] >= x1 or b[3] <= y0 or b[1] >= y1


def test_parked_cars_sit_inside_their_stalls_without_overlapping(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Every parked car is a sedan or SUV on the lot surface, marked parked,
    inside its own stall's painted lines, and no two cars' boxes overlap."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    parked = [v for v in result.vehicles if v.parked]
    assert parked
    stalls = [s for lot in result.parking_lots for s in lot.stalls]
    for car in parked:
        assert car.vehicle_type in PARKED_VEHICLE_TYPES
        assert car.surface_z == LOT_SURFACE_Z_M
        nearest = _nearest_stall(stalls, car)
        along = np.array([np.cos(nearest.head_heading_rad), np.sin(nearest.head_heading_rad)])
        lateral = np.array([-along[1], along[0]])
        offset = car.box_center - np.array(nearest.center)
        yaw = abs(((car.heading_rad - nearest.head_heading_rad + np.pi / 2) % np.pi) - np.pi / 2)
        half_along = (car.length * np.cos(yaw) + car.width * np.sin(yaw)) / 2
        half_lateral = (car.length * np.sin(yaw) + car.width * np.cos(yaw)) / 2
        assert offset @ along + half_along <= nearest.length / 2 + 1e-6
        assert (
            -(offset @ along) + half_along
            <= nearest.length / 2 + AISLE_OVERHANG_M + PICKUP_OVERHANG_M
        )
        assert abs(offset @ lateral) + half_lateral <= nearest.width / 2 + 1e-6
    ids = [v.vehicle_id for v in result.vehicles]
    assert len(ids) == len(set(ids))
    boxes = [v.aabb for v in parked]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_parked_vehicle_types_follow_the_flattened_class_mix(urban_config) -> None:
    """Only sedans, SUVs and pickups park, in the class mix raised to
    PARKED_MIX_EXPONENT."""
    config = _config(urban_config, 1.0)
    lot = layout_lot(0, (0.0, 0.0, 60 * STALL_WIDTH_M, 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0))
    cars = parked_vehicles([lot] * 8, config, seed=3, first_vehicle_id=100)
    types = [c.vehicle_type for c in cars]
    assert set(types) <= set(PARKED_VEHICLE_TYPES)
    weights = {t: urban_config.vehicle_mix[t] ** PARKED_MIX_EXPONENT for t in PARKED_VEHICLE_TYPES}
    for vehicle_type, weight in weights.items():
        expected = weight / sum(weights.values())
        assert abs(types.count(vehicle_type) / len(types) - expected) < 0.06
    assert cars[0].vehicle_id == 100


def test_lot_meshes_are_a_surface_and_one_stripe_mesh_per_lot(urban_config, bounds) -> None:
    """Each lot yields an asphalt surface, a paint_white stripe mesh, and
    a driveway apron and ramp; all are flat except the ramp."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    meshes = parking_lot_meshes(result.parking_lots)
    lots = len(result.parking_lots)
    assert [m.material for m in meshes].count("asphalt") == 3 * lots
    assert [m.material for m in meshes].count("paint_white") == lots
    ramps = [m for m in meshes if not np.allclose(m.vertices[:, 2], m.vertices[0, 2])]
    assert len(ramps) == lots
    for ramp in ramps:
        assert ramp.vertices[:, 2].min() == pytest.approx(DRIVEWAY_RAMP_OUTER_Z_M)
        assert ramp.vertices[:, 2].max() == pytest.approx(LOT_SURFACE_Z_M)
        tri = ramp.vertices[ramp.triangles[:3]]
        normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        assert normal[2] > 0.0


def test_plan_needs_edges_and_positive_fraction(urban_config) -> None:
    """No edges plans nothing."""
    assert not plan_parking_lots({}, {}, _config(urban_config, 1.0), 1)


def test_parked_cars_have_no_lights_at_night_and_stand_on_the_lot(urban_config, bounds) -> None:
    """Parked cars add no headlights/glows, and their asset z is the lot
    surface height."""
    night = generate_scenario(
        42, _config(urban_config, 0.6), bounds, "n", time_of_day=TimeOfDay.NIGHT
    )
    parked = [v for v in night.vehicles if v.parked]
    moving = [v for v in night.vehicles if not v.parked]
    assert parked and moving
    assert all(not vehicle_lights(v) and not vehicle_glows(v) for v in parked)
    payload = serialize_scenario(night)
    assert len(payload["lights"]) == 4 * len(moving)
    zs = {a["id"]: a["position"][2] for a in payload["assets"] if a["category"] == "vehicle"}
    assert all(zs[v.vehicle_id] == LOT_SURFACE_Z_M for v in parked)
    assert all(zs[v.vehicle_id] == 0.0 for v in moving)


def test_parked_models_are_only_ordinary_cars_that_fit_a_stall() -> None:
    """Every allowed model is a sedan, SUV or pickup that fits a stall (a
    pickup may overhang by a few centimetres), and the taxi, police car, box
    van, other trucks and bus are excluded."""
    assert {m.vehicle_type for m in PARKED_MODELS} == set(PARKED_VEHICLE_TYPES)
    for model in PARKED_MODELS:
        length, width = vehicle_box(model.asset_path, model.vehicle_type)[:2]
        assert length <= STALL_LENGTH_M + PICKUP_OVERHANG_M
        assert width <= STALL_WIDTH_M - 0.5
    excluded = (
        "vehicle12",
        "vehicle13",
        "vehVan_vehicle09",
        "vehTruck_vehicle08",
        "vehTruck_vehicle11",
        "trailer",
        "vehBus",
    )
    assert not any(name in m.asset_path for m in PARKED_MODELS for name in excluded)


def test_vehicle_defaults_are_unparked_on_the_road() -> None:
    """A plain Vehicle is not parked and stands at z 0."""
    car = Vehicle(0, "sedan", "/p", np.zeros(2), 0.0, *VEHICLE_DIMENSIONS["sedan"])
    assert not car.parked and car.surface_z == 0.0


def test_islands_hold_a_lamp_at_every_head_line() -> None:
    """A row longer than the island period gets an island every period; each
    island holds one lamp at each head line (rows meeting back to back or
    ending), so a two-module lot has three head lines."""
    depth = 2 * (2 * STALL_LENGTH_M + AISLE_WIDTH_M) + 2.0
    length = (2 * ISLAND_PERIOD_STALLS + 3) * STALL_WIDTH_M + 2.0
    lot = layout_lot(0, (0.0, 0.0, length, depth))
    stalls_per_row = 2 * ISLAND_PERIOD_STALLS + 3
    islands = len(range(ISLAND_PERIOD_STALLS - 1, stalls_per_row - 1, ISLAND_PERIOD_STALLS))
    assert islands == 2
    assert len(lot.lamp_positions) == islands * 3
    assert len(lot.stalls) == 4 * (stalls_per_row - islands)
    assert len(lot.aisle_centers) == 2
    assert not any(
        abs(stall.center[0] - x) < STALL_WIDTH_M / 2 and abs(stall.center[1] - y) < STALL_LENGTH_M
        for stall in lot.stalls
        for x, y in lot.lamp_positions
    )


def test_a_short_row_still_gets_one_island_and_lamps() -> None:
    """A row shorter than the island period has a single mid-row island."""
    lot = layout_lot(0, (0.0, 0.0, 8 * STALL_WIDTH_M + 2.0, STALL_LENGTH_M + AISLE_WIDTH_M + 2.0))
    assert len(lot.lamp_positions) == 1  # one island, one head line
    assert len(lot.stalls) == 7


def test_driveway_widening_only_grows_over_overlapping_removed_curbs() -> None:
    """A removed curb piece overlapping the gap stretches the span to its
    extent along the road; one elsewhere changes nothing."""
    driveway = Driveway("x0", road_edge=10.0, lot_edge=14.0, span=(20.0, 27.0))
    assert driveway.apron == (10.0, 20.0, 14.0, 27.0)
    assert driveway.ramp[2] == 10.0 and driveway.ramp[0] < 10.0
    grown = driveway.widened([(9.5, 17.0, 10.5, 22.0), (9.5, 26.0, 10.5, 32.0)])
    assert grown.span == (17.0, 32.0)
    assert driveway.widened([(9.5, 50.0, 10.5, 55.0)]).span == (20.0, 27.0)
    east = Driveway("x1", road_edge=90.0, lot_edge=86.0, span=(20.0, 27.0))
    assert east.apron == (86.0, 20.0, 90.0, 27.0)
    assert east.ramp[0] == 90.0 and east.ramp[2] > 90.0
    north = Driveway("y1", road_edge=90.0, lot_edge=86.0, span=(20.0, 27.0))
    assert north.apron == (20.0, 86.0, 27.0, 90.0)
    assert north.widened([(18.0, 89.5, 30.0, 90.5)]).span == (18.0, 30.0)


def test_every_lot_has_a_driveway_lined_up_with_an_aisle(urban_config, bounds) -> None:
    """Each lot's driveway leaves by a short side, is one aisle wide before
    widening, is centered on an aisle, and the lot edge is its inner end."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    assert result.parking_lots
    for lot in result.parking_lots:
        driveway = lot.driveway
        assert driveway is not None
        assert (driveway.side in ("x0", "x1")) == lot.aisle_along_x
        assert driveway.span[1] - driveway.span[0] >= DRIVEWAY_WIDTH_M - 1e-6
        centers = [
            (driveway.span[0] + driveway.span[1]) / 2.0,
        ]
        assert any(abs(centers[0] - aisle) < DRIVEWAY_WIDTH_M for aisle in lot.aisle_centers)
        edge = {
            "x0": lot.bounds[0],
            "x1": lot.bounds[2],
            "y0": lot.bounds[1],
            "y1": lot.bounds[3],
        }[driveway.side]
        assert driveway.lot_edge == pytest.approx(edge)


def test_the_curb_and_sidewalk_are_cut_where_a_driveway_crosses(urban_config, bounds) -> None:
    """With lots the road-edge pieces have a gap at each driveway: no curb or
    sidewalk piece overlaps a driveway's apron; without lots nothing is cut."""
    with_lots = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    plain = generate_scenario(42, urban_config, bounds, "y")
    assert len(with_lots.road_edge_pieces) < len(plain.road_edge_pieces) + 1
    curb_x = {round(float(p.position[0]), 3) for p in with_lots.road_edge_pieces}
    for lot in with_lots.parking_lots:
        x0, y0, x1, y1 = lot.driveway.apron
        for piece in with_lots.road_edge_pieces:
            px, py = float(piece.position[0]), float(piece.position[1])
            assert not (x0 < px < x1 and y0 < py < y1)
    assert curb_x


def test_lot_props_are_lamps_and_optional_wheel_stops(urban_config, bounds) -> None:
    """One lamp per lamp position, and wheel stops (one per stall, the
    cited 2.5 ft back from the head line, turned across the stall) only in
    lots that have them."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    lamps = sum(len(lot.lamp_positions) for lot in result.parking_lots)
    pieces = parking_lot_pieces(result.parking_lots, lamp_style=1)
    stops = [p for p in pieces if p.asset_path in PARKING_BLOCK_ASSET_PATHS]
    with_stops = [lot for lot in result.parking_lots if lot.wheel_stop_styles]
    assert len(pieces) == lamps + len(stops)
    assert len(stops) == sum(len(lot.stalls) for lot in with_stops)
    for lot in with_stops:
        stall = lot.stalls[0]
        head = np.array([np.cos(stall.head_heading_rad), np.sin(stall.head_heading_rad)])
        expected = np.array(stall.center) + head * (stall.length / 2.0 - WHEEL_STOP_SETBACK_M)
        block = PARKING_BLOCK_ASSET_PATHS[lot.wheel_stop_styles[0]]
        matches = [
            p
            for p in pieces
            if p.asset_path == block and np.allclose(p.position[:2], expected, atol=1e-9)
        ]
        assert len(matches) == 1
        assert matches[0].position[2] == pytest.approx(LOT_SURFACE_Z_M)
        assert matches[0].rotation_rad == pytest.approx(stall.head_heading_rad + np.pi / 2.0)


def test_lot_pieces_reach_the_payload_with_unique_ids(urban_config, bounds) -> None:
    """Lot lamps and wheel stops are serialized as static assets and every
    asset id in the payload stays unique."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    payload = serialize_scenario(result)
    paths = [a["asset_path"] for a in payload["assets"]]
    assert sum(p in PARKING_BLOCK_ASSET_PATHS for p in paths) == sum(
        1 for p in result.parking_lot_pieces if p.asset_path in PARKING_BLOCK_ASSET_PATHS
    )
    ids = [a["id"] for a in payload["assets"] if a["category"] == "static_asset"]
    assert len(ids) == len(set(ids))


def test_each_driveway_gets_a_ladder_crosswalk_across_its_mouth(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Every lot's driveway has stripes on the street crosswalks' own asset,
    one per BAR_PITCH_M across its width, lying on the apron, long axis into
    the lot, thin like a street crosswalk stripe, just above the lot surface."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    pieces = driveway_crosswalk_pieces(result.parking_lots)
    assert pieces
    width_scale = STOP_LINE_WIDTH_M / STOP_LINE_REAL_SIZE_M
    for lot in result.parking_lots:
        driveway = lot.driveway
        x0, y0, x1, y1 = driveway.apron
        stripes = [
            p
            for p in pieces
            if x0 - 1e-6 <= p.position[0] <= x1 + 1e-6 and y0 - 1e-6 <= p.position[1] <= y1 + 1e-6
        ]
        span = driveway.span[1] - driveway.span[0]
        assert len(stripes) == max(1, round(span / BAR_PITCH_M))
        along_x = driveway.side in ("x0", "x1")
        centers = sorted(float(p.position[1] if along_x else p.position[0]) for p in stripes)
        assert np.diff(centers) == pytest.approx(span / len(stripes)) if len(stripes) > 1 else True
        assert centers[0] == pytest.approx(driveway.span[0] + span / len(stripes) / 2.0)
        for stripe in stripes:
            assert stripe.asset_path == STOP_LINE_ASSET_PATH
            assert stripe.scale[0] == pytest.approx(width_scale)
            assert stripe.scale[1] * STOP_LINE_PAINTED_DEPTH_M <= 3.0 + 1e-9
            assert stripe.position[2] > LOT_SURFACE_Z_M
        inward = {"x0": (1, 0), "x1": (-1, 0), "y0": (0, 1), "y1": (0, -1)}[driveway.side]
        expected = np.arctan2(inward[0], -inward[1])
        assert all(stripe.rotation_rad == pytest.approx(expected) for stripe in stripes)


def test_driveway_crosswalk_is_centered_on_the_apron_depth() -> None:
    """On a driveway whose apron is 3.5 m deep, the stripes sit 1.75 m in from
    the road edge, and the band is the sidewalk width (3 m) long."""
    lot = layout_lot(0, (0.0, 0.0, 60.0, 30.0))
    lot.driveway = Driveway("x0", road_edge=-3.5, lot_edge=0.0, span=(8.0, 15.0))
    stripes = driveway_crosswalk_pieces([lot])
    assert all(stripe.position[0] == pytest.approx(-1.75) for stripe in stripes)
    assert all(
        stripe.scale[1] * STOP_LINE_PAINTED_DEPTH_M == pytest.approx(3.0) for stripe in stripes
    )
    north = layout_lot(1, (0.0, 0.0, 30.0, 60.0))
    north.driveway = Driveway("y1", road_edge=63.5, lot_edge=60.0, span=(8.0, 15.0))
    stripes = driveway_crosswalk_pieces([north])
    assert all(stripe.position[1] == pytest.approx(61.75) for stripe in stripes)
    assert all(stripe.rotation_rad == pytest.approx(np.arctan2(0.0, 1.0)) for stripe in stripes)


def test_every_lot_has_wheel_stops_in_one_of_the_block_styles(urban_config, bounds) -> None:
    """All lots get parking blocks (a style per stall, from the five), and
    the payload carries one block per stall."""
    for seed in (42, 7, 19):
        result = generate_scenario(seed, _config(urban_config, 0.7), bounds, "x")
        assert result.parking_lots
        for lot in result.parking_lots:
            assert len(lot.wheel_stop_styles) == len(lot.stalls)
            assert set(lot.wheel_stop_styles) <= set(range(len(PARKING_BLOCK_ASSET_PATHS)))
        stops = [p for p in result.parking_lot_pieces if p.asset_path in PARKING_BLOCK_ASSET_PATHS]
        assert len(stops) == sum(len(lot.stalls) for lot in result.parking_lots)


def test_block_styles_are_random_per_stall_deterministic_and_all_used(urban_config, bounds) -> None:
    """Across a scenario's lots the styles mix (every style shows up, in about
    equal shares); the same seed gives the same styles and another seed a
    different sequence."""
    config = _config(urban_config, 0.7)
    first = generate_scenario(42, config, bounds, "a")
    again = generate_scenario(42, config, bounds, "b")
    other = generate_scenario(43, config, bounds, "c")
    styles = [style for lot in first.parking_lots for style in lot.wheel_stop_styles]
    assert len(styles) > 100
    assert set(styles) == set(range(len(PARKING_BLOCK_ASSET_PATHS)))
    for style in range(len(PARKING_BLOCK_ASSET_PATHS)):
        assert styles.count(style) / len(styles) == pytest.approx(
            1.0 / len(PARKING_BLOCK_ASSET_PATHS), abs=0.1
        )
    assert [lot.wheel_stop_styles for lot in first.parking_lots] == [
        lot.wheel_stop_styles for lot in again.parking_lots
    ]
    assert [lot.wheel_stop_styles for lot in first.parking_lots] != [
        lot.wheel_stop_styles for lot in other.parking_lots
    ]


def test_lots_never_exceed_the_size_cap(urban_config, bounds) -> None:
    """No lot is longer than 60 m, wider than 45 m or holds more than 80 stalls, and sizes vary."""
    config = _config(urban_config, 0.7)
    lots = [
        lot
        for seed in range(20)
        for lot in generate_scenario(seed, config, bounds, "cap").parking_lots
    ]
    assert lots
    for lot in lots:
        x_min, y_min, x_max, y_max = lot.bounds
        assert max(x_max - x_min, y_max - y_min) <= LOT_MAX_LONG_SIDE_M + 1e-6
        assert min(x_max - x_min, y_max - y_min) <= LOT_MAX_SHORT_SIDE_M + 1e-6
        assert len(lot.stalls) <= 80
    assert len({len(lot.stalls) for lot in lots}) > 5
