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
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.actor_placement import Vehicle, vehicle_box
from src.procedural.building_facade import FacadePiece
from src.procedural.building_placement import identify_city_blocks
from src.procedural.crosswalks import (
    BAR_PITCH_M,
    STOP_LINE_ASSET_PATH,
    STOP_LINE_REAL_SIZE_M,
    STOP_LINE_WIDTH_M,
    STOP_LINE_Z_LIFT_M,
)
from src.procedural.lane_topology import LANE_WIDTH_METERS, SIDEWALK_WIDTH_METERS
from src.procedural.mesh_factory import Mesh, flat_quad_mesh
from src.procedural.road_network import RoadEdge, RoadNode
from src.procedural.scenario import ScenarioTypeConfig
from src.procedural.street_furniture import LAMP_STYLES

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
# A lot's driveway is as wide as its aisles; the ramp is the short slope from
# road level up to the lot surface across the gutter (a design choice: no
# driveway-width source was found).
DRIVEWAY_WIDTH_M = AISLE_WIDTH_M
DRIVEWAY_RAMP_LENGTH_M = 0.8
DRIVEWAY_RAMP_OUTER_Z_M = 0.003

# A landscape island (one stall wide, no stall) is left every this many
# stalls along a row, at the head lines between rows, to hold a light pole.
ISLAND_PERIOD_STALLS = 14

# Wheel stops sit centered in the stall, this far back from its head line
# (2.5 ft, per parking-lot guides), in every lot. Each stall's block is a
# random one of the five yellow-painted concrete styles (they differ in how much
# paint is left and how worn the concrete is), so a row cycles through them.
WHEEL_STOP_SETBACK_M = 2.5 * FEET_TO_METERS
WHEEL_STOP_LOT_FRACTION = 1.0
_PARKING_BLOCK_DIR = "/Game/Megascans/3D_Assets"
# The five Megascans parking blocks (one style per lot), the mesh path of each.
PARKING_BLOCK_ASSET_PATHS: Tuple[str, ...] = (
    f"{_PARKING_BLOCK_DIR}/Parking_Block_00/Parking_Block_LOD0_tltrecmfa",
    f"{_PARKING_BLOCK_DIR}/Parking_Block_01/Parking_Block_LOD0_tlnvfh1fa",
    f"{_PARKING_BLOCK_DIR}/Parking_Block_02/Parking_Block_LOD0_tlovdcvfa",
    f"{_PARKING_BLOCK_DIR}/Parking_Block_03/Parking_Block_LOD0_tlnvfjyfa",
    f"{_PARKING_BLOCK_DIR}/Parking_Block_04/Parking_Block_LOD0_tltqfbxfa",
)

PARKED_VEHICLE_TYPES = ("sedan", "suv", "truck")
# The scenario's class mix, raised to this power before drawing a parked car's
# type. The city sample pool has five suitable sedans but only one suitable
# SUV (a wagon) and one pickup, so the real mix (61% SUV) would fill lots with
# one repeated wagon; 0.5 keeps the ordering but evens the models out.
PARKED_MIX_EXPONENT = 0.5


@dataclass(frozen=True)
class ParkedModel:
    """A City Sample body shell that suits a stall (its real size comes from
    ``vehicle_bounds`` through ``actor_placement.vehicle_box``)."""

    asset_path: str
    vehicle_type: str


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
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle03/Mesh/SM_Frame_vehCar_vehicle03",
        "sedan",
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle05/Mesh/SM_Frame_vehCar_vehicle05",
        "sedan",
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle06/Mesh/SM_Frame_vehCar_vehicle06",
        "sedan",
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehCar_vehicle07/Mesh/SM_Frame_vehCar_vehicle07",
        "sedan",
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehVan_vehicle01/Mesh/SM_Frame_vehVan_vehicle01",
        "suv",
    ),
    ParkedModel(
        f"{_VEHICLE_DIR}/vehTruck_vehicle04/Mesh/SM_Frame_vehTruck_vehicle04",
        "truck",
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


Rect = Tuple[float, float, float, float]


@dataclass(frozen=True)
class Driveway:
    """The lot's opening onto the road it faces.

    ``side`` is the lot side it leaves by (``"x0"``/``"x1"`` for the low/high
    x side, ``"y0"``/``"y1"`` likewise for y). ``road_edge`` is the
    coordinate (x for an x side, y for a y side) of the road pavement's outer
    edge, ``lot_edge`` that of the lot's own edge, and ``span`` the extent
    along the road (y for an x side, x for a y side)."""

    side: str
    road_edge: float
    lot_edge: float
    span: Tuple[float, float]

    def _rect(self, near: float, far: float) -> Rect:
        low, high = sorted((near, far))
        if self.side in ("x0", "x1"):
            return low, self.span[0], high, self.span[1]
        return self.span[0], low, self.span[1], high

    @property
    def _away(self) -> float:
        """Signed distance the ramp reaches beyond the road edge."""
        return -DRIVEWAY_RAMP_LENGTH_M if self.side in ("x0", "y0") else DRIVEWAY_RAMP_LENGTH_M

    @property
    def apron(self) -> Rect:
        """The level asphalt from the road edge to the lot's edge."""
        return self._rect(self.road_edge, self.lot_edge)

    @property
    def ramp(self) -> Rect:
        """The slope from road level up to the apron, on the road's side of
        the pavement edge."""
        return self._rect(self.road_edge + self._away, self.road_edge)

    @property
    def gap(self) -> Rect:
        """Everything the driveway covers, for cutting curb and sidewalk."""
        return self._rect(self.road_edge + self._away, self.lot_edge)

    def widened(self, removed_curbs: Sequence[Rect]) -> "Driveway":
        """The driveway grown along the road to cover every curb piece that
        was cut away for it, so no bare gap is left beside the asphalt."""
        gap = self.gap
        low, high = self.span
        along = (1, 3) if self.side in ("x0", "x1") else (0, 2)
        for rect in removed_curbs:
            if rect[2] <= gap[0] or gap[2] <= rect[0] or rect[3] <= gap[1] or gap[3] <= rect[1]:
                continue
            low = min(low, rect[along[0]])
            high = max(high, rect[along[1]])
        return Driveway(self.side, self.road_edge, self.lot_edge, (low, high))


@dataclass
class ParkingLot:  # pylint: disable=too-many-instance-attributes
    """A surface lot: its axis-aligned bounds, stalls and painted stripes
    (``(x_min, y_min, x_max, y_max)`` rectangles), the aisles' center lines,
    the light-pole spots, an optional driveway and the parking-block style
    of each stall's wheel stop (one per stall, empty for a lot without them)."""

    lot_id: int
    bounds: Rect
    stalls: List[ParkingStall] = field(default_factory=list)
    stripes: List[Rect] = field(default_factory=list)
    aisle_along_x: bool = True
    aisle_centers: List[float] = field(default_factory=list)
    lamp_positions: List[Tuple[float, float]] = field(default_factory=list)
    driveway: Optional[Driveway] = None
    wheel_stop_styles: List[int] = field(default_factory=list)

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


def layout_lot(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    lot_id: int, bounds: Tuple[float, float, float, float]
) -> ParkingLot:
    """Stalls and stripes for a lot filling ``bounds``. The aisles run along
    the longer side; an empty lot (no stalls) comes back when the rectangle
    is too small for at least one aisle with a row of ``MIN_STALLS_PER_ROW``
    stalls."""
    x_min, y_min, x_max, y_max = bounds
    aisle_along_x = (x_max - x_min) >= (y_max - y_min)
    lot = ParkingLot(lot_id=lot_id, bounds=bounds, aisle_along_x=aisle_along_x)
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

    # Each row: (v of its center, +1 if its cars face +v when head-in); the
    # aisles' v centers; and the v of every head line rows meet or end at.
    rows: List[Tuple[float, int]] = []
    aisles: List[float] = []
    head_lines: List[float] = []
    if modules == 0:
        used = STALL_LENGTH_M + AISLE_WIDTH_M
        start = v_min + LOT_EDGE_MARGIN_M + (usable_v - used) / 2.0
        rows.append((start + AISLE_WIDTH_M + STALL_LENGTH_M / 2.0, 1))
        aisles.append(start + AISLE_WIDTH_M / 2.0)
        head_lines.append(start + AISLE_WIDTH_M + STALL_LENGTH_M)
    else:
        used = modules * module_depth
        start = v_min + LOT_EDGE_MARGIN_M + (usable_v - used) / 2.0
        for k in range(modules):
            base = start + k * module_depth
            rows.append((base + STALL_LENGTH_M / 2.0, -1))
            rows.append((base + STALL_LENGTH_M + AISLE_WIDTH_M + STALL_LENGTH_M / 2.0, 1))
            aisles.append(base + STALL_LENGTH_M + AISLE_WIDTH_M / 2.0)
            head_lines.append(base)
        head_lines.append(start + modules * module_depth)
    lot.aisle_centers = [float(v) for v in aisles]

    # A landscape island (no stall) every ISLAND_PERIOD_STALLS along the rows,
    # or one mid-row when the row is shorter, holds a pole at each head line.
    islands = set(range(ISLAND_PERIOD_STALLS - 1, stalls_per_row - 1, ISLAND_PERIOD_STALLS))
    if not islands:
        islands = {stalls_per_row // 2}

    u_start = u_min + LOT_EDGE_MARGIN_M + (usable_u - stalls_per_row * STALL_WIDTH_M) / 2.0
    half_stripe = STRIPE_WIDTH_M / 2.0
    for island in sorted(islands):
        u = u_start + (island + 0.5) * STALL_WIDTH_M
        for head_v in head_lines:
            x, y = (u, head_v) if aisle_along_x else (head_v, u)
            lot.lamp_positions.append((float(x), float(y)))
    for row_v, facing in rows:
        for i in range(stalls_per_row):
            if i in islands:
                continue
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
        side_draw = int(rng.integers(0, 2))
        aisle_draw = float(rng.random())
        stops_draw = bool(rng.random() < WHEEL_STOP_LOT_FRACTION)
        if not chosen:
            continue
        x_min, y_min, x_max, y_max = _block_free_rectangle(block, inset)
        if x_max <= x_min or y_max <= y_min:
            continue
        width = (x_max - x_min) * float(frac_x)
        depth = (y_max - y_min) * float(frac_y)
        lot_x = x_min + (x_max - x_min - width) * int(anchor_x)
        lot_y = y_min + (y_max - y_min - depth) * int(anchor_y)
        # The driveway leaves by one of the two short sides (the ends of the
        # aisles); the lot is slid flush against that side of the block's
        # free area, so the driveway only has to cross the sidewalk.
        pavement_edge = max(edge.num_lanes for edge in edges.values()) * LANE_WIDTH_METERS
        block_min, block_max = block.min(axis=0), block.max(axis=0)
        if width >= depth:
            side = "x0" if side_draw == 0 else "x1"
            lot_x = x_min if side == "x0" else x_max - width
            road_edge = float(
                block_min[0] + pavement_edge if side == "x0" else block_max[0] - pavement_edge
            )
        else:
            side = "y0" if side_draw == 0 else "y1"
            lot_y = y_min if side == "y0" else y_max - depth
            road_edge = float(
                block_min[1] + pavement_edge if side == "y0" else block_max[1] - pavement_edge
            )
        lot = layout_lot(len(lots), (lot_x, lot_y, lot_x + width, lot_y + depth))
        if not lot.stalls:
            continue
        aisle_index = min(int(aisle_draw * len(lot.aisle_centers)), len(lot.aisle_centers) - 1)
        aisle = lot.aisle_centers[aisle_index]
        lot_edge = {
            "x0": lot.bounds[0],
            "x1": lot.bounds[2],
            "y0": lot.bounds[1],
            "y1": lot.bounds[3],
        }[side]
        half = DRIVEWAY_WIDTH_M / 2.0
        lot.driveway = Driveway(side, road_edge, lot_edge, (aisle - half, aisle + half))
        if stops_draw:
            styles = np.random.Generator(np.random.PCG64([seed, 0x9A83, lot.lot_id]))
            lot.wheel_stop_styles = [
                int(style)
                for style in styles.integers(len(PARKING_BLOCK_ASSET_PATHS), size=len(lot.stalls))
            ]
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
            length, width, height, offset_x, offset_y, z_min = vehicle_box(
                model.asset_path, model.vehicle_type
            )
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
            box_center = (
                np.array(stall.center)
                + along * along_offset
                + lateral * lateral_unit * lateral_slack
            )
            turned = heading + yaw
            offset_world = np.array(
                [
                    offset_x * np.cos(turned) - offset_y * np.sin(turned),
                    offset_x * np.sin(turned) + offset_y * np.cos(turned),
                ]
            )
            center = box_center - offset_world
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
                    box_offset=(offset_x, offset_y),
                    box_z_min=z_min,
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


def _ramp_mesh(driveway: Driveway) -> Mesh:
    """The slope from road level (outer edge) up to the lot surface (at the
    road's pavement edge), as one quad."""
    x_min, y_min, x_max, y_max = driveway.ramp
    low, high = DRIVEWAY_RAMP_OUTER_Z_M, LOT_SURFACE_Z_M
    if driveway.side == "x0":
        corners = [
            (x_min, y_min, low),
            (x_max, y_min, high),
            (x_max, y_max, high),
            (x_min, y_max, low),
        ]
    elif driveway.side == "x1":
        corners = [
            (x_max, y_min, low),
            (x_min, y_min, high),
            (x_min, y_max, high),
            (x_max, y_max, low),
        ]
    elif driveway.side == "y0":
        corners = [
            (x_min, y_min, low),
            (x_max, y_min, low),
            (x_max, y_max, high),
            (x_min, y_max, high),
        ]
    else:
        corners = [
            (x_min, y_max, low),
            (x_max, y_max, low),
            (x_max, y_min, high),
            (x_min, y_min, high),
        ]
    vertices = np.array(corners, dtype=np.float64)
    # Wind both triangles counter-clockwise seen from above.
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(corners, corners[1:] + corners[:1]))
    triangles = [0, 1, 2, 0, 2, 3] if area > 0 else [0, 2, 1, 0, 3, 2]
    return Mesh(
        vertices=vertices,
        triangles=np.array(triangles, dtype=np.int64),
        uvs=vertices[:, :2] / LOT_UV_TILE_METERS,
        material="asphalt",
    )


def parking_lot_meshes(lots: Sequence[ParkingLot]) -> List[Mesh]:
    """Each lot's asphalt surface, its painted stall stripes as a second
    mesh, and its driveway's level apron and ramp."""
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
        if lot.driveway is not None:
            a_x0, a_y0, a_x1, a_y1 = lot.driveway.apron
            meshes.append(
                flat_quad_mesh(
                    a_x0, a_y0, a_x1, a_y1, LOT_SURFACE_Z_M, LOT_UV_TILE_METERS, "asphalt"
                )
            )
            meshes.append(_ramp_mesh(lot.driveway))
    return meshes


def parking_lot_pieces(lots: Sequence[ParkingLot], lamp_style: int = 0) -> List[FacadePiece]:
    """The static props of every lot: a light pole at each island (in the
    scenario's own street-lamp style) and, in lots that have them, a parking
    block centered in every stall, ``WHEEL_STOP_SETBACK_M`` back from the
    stall's head line and turned across the stall."""
    lamp_path, lamp_rotation = LAMP_STYLES[lamp_style % len(LAMP_STYLES)]
    pieces: List[FacadePiece] = []
    for lot in lots:
        for x, y in lot.lamp_positions:
            pieces.append(
                FacadePiece(lamp_path, np.array([x, y, LOT_SURFACE_Z_M]), float(lamp_rotation))
            )
        for stall, style in zip(lot.stalls, lot.wheel_stop_styles):
            block_path = PARKING_BLOCK_ASSET_PATHS[style]
            head = np.array([np.cos(stall.head_heading_rad), np.sin(stall.head_heading_rad)])
            position = np.array(stall.center) + head * (stall.length / 2.0 - WHEEL_STOP_SETBACK_M)
            pieces.append(
                FacadePiece(
                    block_path,
                    np.array([position[0], position[1], LOT_SURFACE_Z_M]),
                    float(stall.head_heading_rad + np.pi / 2.0),
                )
            )
    return pieces


# The bar mesh's painted length per unit of its Y scale, measured live: at Y
# scales 0.5, 1, 2, 3 and 4 the painted length came out at 0.263-0.270 of
# the mesh's X extent per unit scale, and the X extent is
# STOP_LINE_REAL_SIZE_M (5.12 m) per unit scale.
STOP_LINE_PAINTED_DEPTH_M = STOP_LINE_REAL_SIZE_M * 0.267

# Direction into the lot from each driveway side (python frame).
_INWARD = {"x0": (1.0, 0.0), "x1": (-1.0, 0.0), "y0": (0.0, 1.0), "y1": (0.0, -1.0)}


def _crosswalk_stripes(  # pylint: disable=too-many-locals
    driveway: Driveway,
) -> List[FacadePiece]:
    """One driveway's crosswalk stripes (see ``driveway_crosswalk_pieces``)."""
    inward = _INWARD[driveway.side]
    apron_length = abs(driveway.lot_edge - driveway.road_edge)
    depth_scale = min(SIDEWALK_WIDTH_METERS, apron_length) / STOP_LINE_PAINTED_DEPTH_M
    width_scale = STOP_LINE_WIDTH_M / STOP_LINE_REAL_SIZE_M
    rotation = float(np.arctan2(inward[0], -inward[1]))
    low, high = driveway.span
    count = max(1, round((high - low) / BAR_PITCH_M))
    pitch = (high - low) / count
    depth_middle = driveway.road_edge + (inward[0] + inward[1]) * apron_length / 2.0
    stripes: List[FacadePiece] = []
    for i in range(count):
        across = low + pitch * (i + 0.5)
        x, y = (depth_middle, across) if driveway.side in ("x0", "x1") else (across, depth_middle)
        stripes.append(
            FacadePiece(
                STOP_LINE_ASSET_PATH,
                np.array([x, y, LOT_SURFACE_Z_M + STOP_LINE_Z_LIFT_M]),
                rotation,
                (width_scale, depth_scale, 1.0),
            )
        )
    return stripes


def driveway_crosswalk_pieces(lots: Sequence[ParkingLot]) -> List[FacadePiece]:
    """A continental (ladder) crosswalk across each driveway mouth, so
    pedestrians on the sidewalk cross where cars enter the lot. It uses the
    street crosswalks' own bar asset, bar width and pitch: the bars run along
    the driveway (into the lot), one bar every ``BAR_PITCH_M`` across the
    driveway's width, over the sidewalk-wide strip of the apron."""
    pieces: List[FacadePiece] = []
    for lot in lots:
        if lot.driveway is not None:
            pieces += _crosswalk_stripes(lot.driveway)
    return pieces
