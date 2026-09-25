"""Surface parking lots: a lot's stall layout, its parked cars and its
ground surface, so generated cities are not only buildings and streets.

A lot takes a rectangle of a city block, inset behind the roads' pavement
and the sidewalk (the same margin buildings keep). Its stalls are
perpendicular (90 degree) in double-loaded rows around aisles running along
the lot's long side.

Dimensions are the US perpendicular-stall figures quoted by parking-design
guides citing the ITE (secondary sources, not the standard itself): a stall
is 9 ft wide by 18 ft long (ITE recommends 9.0 x 18.5 ft) and a two-way
90-degree aisle is 24 ft. City Sample's buildings are US city styles, so the
US figures apply. Stripe width (4 in) is the common painted-line width.

Which blocks become lots, how large a lot is, each lot's occupancy and how a
car sits in its stall are randomized from dedicated RNG streams (nothing else
in a scenario changes). The ranges are design choices, not measurements: no
occupancy statistics were sourced.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.actor_placement import Vehicle
from src.procedural.building_placement import identify_city_blocks
from src.procedural.lane_topology import LANE_WIDTH_METERS, SIDEWALK_WIDTH_METERS
from src.procedural.mesh_factory import Mesh, flat_quad_mesh
from src.procedural.road_network import RoadEdge, RoadNode
from src.procedural.scenario import ScenarioTypeConfig

FEET_TO_METERS = 0.3048
STALL_WIDTH_M = 9.0 * FEET_TO_METERS
STALL_LENGTH_M = 18.0 * FEET_TO_METERS
AISLE_WIDTH_M = 24.0 * FEET_TO_METERS
STRIPE_WIDTH_M = (4.0 / 12.0) * FEET_TO_METERS

# Clear border between the lot's edge and its outermost stalls/aisles.
LOT_EDGE_MARGIN_M = 1.0
# Extra gap between a lot and the road pavement/sidewalk around its block.
LOT_BLOCK_INSET_MARGIN_M = 0.5
# Slack (metres) when counting how many stalls or modules fit, so an exact
# fit is not lost to floating-point rounding.
FIT_TOLERANCE_M = 1e-6
# A lot needs at least this many stalls per row to be worth drawing.
MIN_STALLS_PER_ROW = 4

# The lot surface sits just above the block paving (0.10 m, see
# block_pavement.py) and below the sidewalk slabs' top; stripes sit just
# above the surface so they never z-fight with it.
LOT_SURFACE_Z_M = 0.11
STRIPE_Z_M = 0.115
LOT_UV_TILE_METERS = 4.0

# A lot covers between these fractions of its block's free interior along
# each axis (1.0 = the whole interior).
LOT_EXTENT_FRACTION_RANGE = (0.5, 1.0)
# Share of a lot's stalls that hold a car, drawn once per lot.
PARKED_OCCUPANCY_RANGE = (0.3, 0.9)
# Share of cars that back into their stall (the rest drive in nose-first).
BACK_IN_FRACTION = 0.15
# A parked car's yaw error from square (radians, truncated), and the clear
# gap it keeps from its stall's painted lines.
PARK_YAW_STD_RAD = 0.02
PARK_YAW_MAX_RAD = 0.06
STALL_LINE_CLEARANCE_M = 0.1
# How far toward the aisle a car may stand beyond its stall's tail line.
AISLE_OVERHANG_M = 0.25
PARKED_VEHICLE_TYPES = ("sedan", "suv", "truck")
# The scenario's class mix, raised to this power before drawing a parked car's
# type. The city sample pool has five suitable sedans but only one suitable
# SUV (a wagon) and one pickup, so the real mix (61% SUV) would fill lots with
# one repeated wagon; 0.5 keeps the ordering but evens the models out.
PARKED_MIX_EXPONENT = 0.5


@dataclass(frozen=True)
class ParkedModel:
    """A City Sample body shell that suits a stall, with its real size."""

    asset_path: str
    vehicle_type: str
    length: float
    width: float
    height: float


# Real bounds of each body-shell mesh, read live from the engine with
# GetStaticMeshBounds (full extents in metres; height is the top of the box).
# Only models that read as an ordinary private vehicle and (nearly) fit a
# stall. Left out, identified by rendering each model: vehicle12 (yellow taxi
# with a roof sign), vehicle13 (police cruiser), vehVan_vehicle09 (box van),
# the other trucks, the trailer and the bus. The pickup (vehTruck_vehicle04)
# is 5.55 m, a few centimetres over a stall, like a real pickup.
_VEHICLE_DIR = "/Game/Vehicle"
PARKED_MODELS: Tuple[ParkedModel, ...] = (
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02",
        "sedan",
        4.789,
        1.880,
        1.755,
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle03/Mesh/SM_Frame_vehCar_vehicle03",
        "sedan",
        5.400,
        1.985,
        1.523,
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle05/Mesh/SM_Frame_vehCar_vehicle05",
        "sedan",
        4.525,
        1.773,
        1.704,
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle06/Mesh/SM_Frame_vehCar_vehicle06",
        "sedan",
        4.367,
        1.782,
        1.376,
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle07/Mesh/SM_Frame_vehCar_vehicle07",
        "sedan",
        4.410,
        1.715,
        1.431,
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehVan_vehicle01/Mesh/SM_Frame_vehVan_vehicle01",
        "suv",
        4.791,
        1.883,
        1.859,
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehTruck_vehicle04/Mesh/SM_Frame_vehTruck_vehicle04",
        "truck",
        5.555,
        1.993,
        1.838,
    ),
)


@dataclass(frozen=True)
class ParkingStall:
    """One stall: its center, and the direction a car faces when it drives
    in nose-first (pointing away from the aisle, toward the stall's head)."""

    center: Tuple[float, float]
    head_heading_rad: float
    width: float = STALL_WIDTH_M
    length: float = STALL_LENGTH_M


@dataclass
class ParkingLot:
    """A surface lot: its axis-aligned bounds, stalls and painted stripes
    (``(x_min, y_min, x_max, y_max)`` rectangles)."""

    lot_id: int
    bounds: Tuple[float, float, float, float]
    stalls: List[ParkingStall] = field(default_factory=list)
    stripes: List[Tuple[float, float, float, float]] = field(default_factory=list)

    @property
    def aabb(self) -> Tuple[float, float, float, float]:
        """The lot's bounds, named like ``Building.aabb`` so keep-out
        checks treat both alike."""
        return self.bounds


def _block_free_rectangle(
    block: npt.NDArray[np.float64], inset: float
) -> Tuple[float, float, float, float]:
    """A block's bounding rectangle inset on every side."""
    x_min, y_min = block.min(axis=0) + inset
    x_max, y_max = block.max(axis=0) - inset
    return float(x_min), float(y_min), float(x_max), float(y_max)


def layout_lot(  # pylint: disable=too-many-locals
    lot_id: int, bounds: Tuple[float, float, float, float]
) -> ParkingLot:
    """Stalls and stripes for a lot filling ``bounds``. The aisles run along
    the longer side; an empty lot (no stalls) comes back when the rectangle
    is too small for at least one aisle with a row of ``MIN_STALLS_PER_ROW``
    stalls."""
    x_min, y_min, x_max, y_max = bounds
    lot = ParkingLot(lot_id=lot_id, bounds=bounds)
    aisle_along_x = (x_max - x_min) >= (y_max - y_min)
    # (u, v): u runs along the aisles, v across them.
    u_min, u_max, v_min, v_max = (
        (x_min, x_max, y_min, y_max) if aisle_along_x else (y_min, y_max, x_min, x_max)
    )
    usable_u = (u_max - u_min) - 2.0 * LOT_EDGE_MARGIN_M
    usable_v = (v_max - v_min) - 2.0 * LOT_EDGE_MARGIN_M
    stalls_per_row = int((usable_u + FIT_TOLERANCE_M) // STALL_WIDTH_M)
    module_depth = 2.0 * STALL_LENGTH_M + AISLE_WIDTH_M
    modules = int((usable_v + FIT_TOLERANCE_M) // module_depth)
    if stalls_per_row < MIN_STALLS_PER_ROW:
        return lot
    if modules == 0 and usable_v + FIT_TOLERANCE_M < STALL_LENGTH_M + AISLE_WIDTH_M:
        return lot

    # Each row: (v of its center, +1 if its cars face +v when head-in).
    rows: List[Tuple[float, int]] = []
    if modules == 0:
        used = STALL_LENGTH_M + AISLE_WIDTH_M
        start = v_min + LOT_EDGE_MARGIN_M + (usable_v - used) / 2.0
        rows.append((start + AISLE_WIDTH_M + STALL_LENGTH_M / 2.0, 1))
    else:
        used = modules * module_depth
        start = v_min + LOT_EDGE_MARGIN_M + (usable_v - used) / 2.0
        for k in range(modules):
            base = start + k * module_depth
            rows.append((base + STALL_LENGTH_M / 2.0, -1))
            rows.append((base + STALL_LENGTH_M + AISLE_WIDTH_M + STALL_LENGTH_M / 2.0, 1))

    u_start = u_min + LOT_EDGE_MARGIN_M + (usable_u - stalls_per_row * STALL_WIDTH_M) / 2.0
    half_stripe = STRIPE_WIDTH_M / 2.0
    for row_v, facing in rows:
        for i in range(stalls_per_row):
            u = u_start + (i + 0.5) * STALL_WIDTH_M
            x, y = (u, row_v) if aisle_along_x else (row_v, u)
            if aisle_along_x:
                head = np.pi / 2.0 * facing
            else:
                head = 0.0 if facing > 0 else np.pi
            lot.stalls.append(ParkingStall(center=(float(x), float(y)), head_heading_rad=head))
        v_low = row_v - STALL_LENGTH_M / 2.0
        v_high = row_v + STALL_LENGTH_M / 2.0
        for i in range(stalls_per_row + 1):
            u = u_start + i * STALL_WIDTH_M
            if aisle_along_x:
                lot.stripes.append((u - half_stripe, v_low, u + half_stripe, v_high))
            else:
                lot.stripes.append((v_low, u - half_stripe, v_high, u + half_stripe))
    return lot


def plan_parking_lots(  # pylint: disable=too-many-locals
    nodes: Dict[int, RoadNode],
    edges: Dict[int, RoadEdge],
    config: ScenarioTypeConfig,
    seed: int,
) -> List[ParkingLot]:
    """Choose which city blocks hold a surface lot and lay each one out.
    ``config.parking_lot_fraction`` of the blocks (in expectation) get a lot;
    zero (the default) returns no lots and draws nothing that any other
    generator uses."""
    if config.parking_lot_fraction <= 0.0 or not edges:
        return []
    rng = np.random.Generator(np.random.PCG64([seed, 0x9A81]))
    inset = (
        max(edge.num_lanes for edge in edges.values()) * LANE_WIDTH_METERS
        + max(config.road_setback_meters, SIDEWALK_WIDTH_METERS)
        + LOT_BLOCK_INSET_MARGIN_M
    )
    lots: List[ParkingLot] = []
    for block in identify_city_blocks(nodes, edges):
        # Every draw happens for every block so the stream stays aligned.
        chosen = rng.random() < config.parking_lot_fraction
        frac_x, frac_y = rng.uniform(*LOT_EXTENT_FRACTION_RANGE, size=2)
        anchor_x, anchor_y = rng.integers(0, 2, size=2)
        if not chosen:
            continue
        x_min, y_min, x_max, y_max = _block_free_rectangle(block, inset)
        if x_max <= x_min or y_max <= y_min:
            continue
        width = (x_max - x_min) * float(frac_x)
        depth = (y_max - y_min) * float(frac_y)
        lot_x = x_min + (x_max - x_min - width) * int(anchor_x)
        lot_y = y_min + (y_max - y_min - depth) * int(anchor_y)
        lot = layout_lot(len(lots), (lot_x, lot_y, lot_x + width, lot_y + depth))
        if lot.stalls:
            lots.append(lot)
    return lots


def _parked_model(rng: np.random.Generator, vehicle_mix: Dict[str, float]) -> ParkedModel:
    """A sedan, SUV or pickup type drawn from the scenario's class mix
    (flattened, see ``PARKED_MIX_EXPONENT``; a bus or delivery truck does not
    fit a stall), then one of that type's suitable models."""
    weights = (
        np.array([vehicle_mix.get(name, 0.0) for name in PARKED_VEHICLE_TYPES], dtype=float)
        ** PARKED_MIX_EXPONENT
    )
    if weights.sum() <= 0.0:
        weights = np.array([1.0, 0.0, 0.0])
    vehicle_type = PARKED_VEHICLE_TYPES[int(rng.choice(len(weights), p=weights / weights.sum()))]
    models = [model for model in PARKED_MODELS if model.vehicle_type == vehicle_type]
    return models[int(rng.integers(len(models)))]


def parked_vehicles(  # pylint: disable=too-many-locals
    lots: Sequence[ParkingLot],
    config: ScenarioTypeConfig,
    seed: int,
    first_vehicle_id: int,
) -> List[Vehicle]:
    """Cars parked in the lots' stalls: each lot draws an occupancy, each
    stall is filled with that probability, and a car sits within its stall
    with a small lateral and lengthwise offset and a slight yaw error, never
    touching the stall's lines."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x9A82]))
    vehicles: List[Vehicle] = []
    for lot in lots:
        occupancy = float(rng.uniform(*PARKED_OCCUPANCY_RANGE))
        for stall in lot.stalls:
            # Fixed number of draws per stall keeps later stalls' cars
            # independent of whether earlier ones were filled.
            filled = rng.random() < occupancy
            back_in = rng.random() < BACK_IN_FRACTION
            lateral_unit, along_unit, yaw_draw = rng.uniform(-1.0, 1.0, size=3)
            model = _parked_model(rng, config.vehicle_mix)
            if not filled:
                continue
            length, width, height = model.length, model.width, model.height
            lateral_slack = max(
                0.0,
                (stall.width - width) / 2.0
                - STALL_LINE_CLEARANCE_M
                - (length / 2.0) * np.sin(PARK_YAW_MAX_RAD),
            )
            # Toward the stall's head the car keeps clear of the line (a car
            # longer than the stall is pushed back toward the aisle instead,
            # so head-to-head rows never touch); toward the aisle it may
            # overhang the tail line a little.
            head_room = (stall.length - length) / 2.0 - STALL_LINE_CLEARANCE_M
            back_room = max(head_room, 0.0) + AISLE_OVERHANG_M
            along_offset = -back_room + (along_unit + 1.0) / 2.0 * (head_room + back_room)
            heading = stall.head_heading_rad + (np.pi if back_in else 0.0)
            yaw = float(
                np.clip(yaw_draw * PARK_YAW_STD_RAD * 2.0, -PARK_YAW_MAX_RAD, PARK_YAW_MAX_RAD)
            )
            along = np.array([np.cos(stall.head_heading_rad), np.sin(stall.head_heading_rad)])
            lateral = np.array([-along[1], along[0]])
            center = (
                np.array(stall.center)
                + along * along_offset
                + lateral * lateral_unit * lateral_slack
            )
            vehicles.append(
                Vehicle(
                    vehicle_id=first_vehicle_id + len(vehicles),
                    vehicle_type=model.vehicle_type,
                    asset_path=model.asset_path,
                    center=center,
                    heading_rad=float(heading + yaw),
                    length=length,
                    width=width,
                    height=height,
                    parked=True,
                    surface_z=LOT_SURFACE_Z_M,
                )
            )
    return vehicles


def _stripe_mesh(stripes: Sequence[Tuple[float, float, float, float]]) -> Mesh:
    """All of a lot's painted stripes as one mesh of upward-facing quads."""
    vertices: List[List[float]] = []
    triangles: List[int] = []
    for x_min, y_min, x_max, y_max in stripes:
        base = len(vertices)
        vertices += [
            [x_min, y_min, STRIPE_Z_M],
            [x_max, y_min, STRIPE_Z_M],
            [x_max, y_max, STRIPE_Z_M],
            [x_min, y_max, STRIPE_Z_M],
        ]
        triangles += [base, base + 1, base + 2, base, base + 2, base + 3]
    verts = np.array(vertices, dtype=np.float64)
    return Mesh(
        vertices=verts,
        triangles=np.array(triangles, dtype=np.int64),
        uvs=verts[:, :2] / LOT_UV_TILE_METERS,
        material="paint_white",
    )


def parking_lot_meshes(lots: Sequence[ParkingLot]) -> List[Mesh]:
    """Each lot's asphalt surface, and its painted stall stripes as a
    second mesh."""
    meshes: List[Mesh] = []
    for lot in lots:
        x_min, y_min, x_max, y_max = lot.bounds
        meshes.append(
            flat_quad_mesh(
                x_min, y_min, x_max, y_max, LOT_SURFACE_Z_M, LOT_UV_TILE_METERS, "asphalt"
            )
        )
        if lot.stripes:
            meshes.append(_stripe_mesh(lot.stripes))
    return meshes
