"""End-to-end scenario and dataset generation, tying together every
procedural/sensor/ground-truth/export module built in Phases 1-6.

Implements MASTER_PROMPT Section 3.1's `generate_dataset.py` CLI entry
point's underlying logic (the CLI script itself is in ``bin/``), and is
the natural home for Phase 6's "Round-trip serialization" and "Export
performance" test bullets -- both require an actual full pipeline run to
test at all.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.export.coco_exporter import CocoFrame, export_coco
from src.export.metadata_manager import ScenarioMetadata, build_scenario_metadata
from src.ground_truth.bbox_2d import project_bboxes_3d_to_2d
from src.ground_truth.bbox_3d import (
    extract_bboxes_3d,
    extract_bboxes_3d_pedestrians,
    extract_bboxes_3d_vehicles,
)
from src.ground_truth.occlusion import filter_occluded
from src.procedural.actor_placement import ActorPlacementGenerator, Pedestrian, Vehicle
from src.procedural.building_colors import draw_building_palettes
from src.procedural.building_facade import FacadePiece, generate_building_facade_pieces
from src.procedural.building_lights import building_piece_room_ids, building_pieces_lit
from src.procedural.building_placement import Building, BuildingPlacementGenerator
from src.procedural.city_sample_assets import BUILDING_STYLES
from src.procedural.crosswalks import generate_crosswalk_pieces
from src.procedural.environment import Season, TimeOfDay, season_has_trees
from src.procedural.lane_connectivity import LaneConnectivityGenerator, LaneConnectivityGraph
from src.procedural.lane_topology import Lane, LaneTopologyGenerator
from src.procedural.mesh_factory import Mesh, MeshFactory
from src.procedural.parking_lots import (
    ParkingLot,
    driveway_crosswalk_pieces,
    parked_vehicles,
    parking_lot_meshes,
    parking_lot_pieces,
    plan_parking_lots,
)
from src.procedural.road_edge_kit import DEFAULT_ROAD_EDGE_KIT, Rect, generate_road_edge_pieces
from src.procedural.road_network import RoadEdge, RoadNetworkGenerator, RoadNode
from src.procedural.scenario import ScenarioTypeConfig
from src.procedural.street_furniture import (
    LAMP_STYLES,
    TREE_BASE_STYLES,
    generate_street_furniture_pieces,
)
from src.procedural.traffic_lights import generate_traffic_light_pieces
from src.procedural.traffic_network import TrafficNetwork, TrafficNetworkGenerator
from src.procedural.validator import ScenarioValidator, ValidationReport
from src.procedural.vehicle_colors import assign_vehicle_paint
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.validation.sanity_checker import SanityReport, check_annotation_count_consistency

Bounds = Tuple[float, float, float, float]


@dataclass
class ScenarioResult:  # pylint: disable=too-many-instance-attributes
    """Everything generated for one scenario (Phases 1-3 output).

    A plain data container aggregating the output of every generator
    from Phases 1-3; the attribute count reflects that, not a design
    smell -- see RoadNode/RoadEdge's own docstrings in road_network.py
    for the same rationale.
    """

    scenario_id: str
    nodes: Dict[int, RoadNode]
    edges: Dict[int, RoadEdge]
    lanes: Dict[int, Lane]
    buildings: List[Building]
    traffic: TrafficNetwork
    lane_connectivity: LaneConnectivityGraph
    vehicles: List[Vehicle]
    pedestrians: List[Pedestrian]
    meshes: List[Mesh]
    building_facade_pieces: List[FacadePiece]
    road_edge_pieces: List[FacadePiece]
    street_furniture_pieces: List[FacadePiece]
    crosswalk_pieces: List[FacadePiece]
    traffic_light_pieces: List[FacadePiece]
    season: Season
    validation_report: ValidationReport
    time_of_day: TimeOfDay = TimeOfDay.DAY
    # The wall palette index (see building_colors.py) of each entry of
    # building_facade_pieces, drawn once per building.
    building_piece_palettes: List[int] = field(default_factory=list)
    # Night only: whether each entry of building_facade_pieces is lit.
    building_pieces_lit: List[bool] = field(default_factory=list)
    parking_lots: List[ParkingLot] = field(default_factory=list)
    parking_lot_pieces: List[FacadePiece] = field(default_factory=list)
    building_piece_room_ids: List[int] = field(default_factory=list)


@dataclass
class DatasetGenerationResult:
    """Summary of one full dataset generation run."""

    num_scenarios: int
    num_frames: int
    coco_path: Path
    metadata_paths: List[Path]
    sanity_report: SanityReport
    elapsed_seconds: float


def _draw_season(style_rng: np.random.Generator) -> Season:
    """One of the four seasons, uniformly, from the scenario's style stream."""
    seasons = list(Season)
    return seasons[int(style_rng.integers(len(seasons)))]


def generate_scenario(  # pylint: disable=too-many-locals,too-many-arguments
    seed: int,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    scenario_id: str,
    season: Optional[Season] = None,
    time_of_day: TimeOfDay = TimeOfDay.DAY,
) -> ScenarioResult:
    """Run the full Phase 1-4 procedural pipeline for one scenario:
    road network -> lanes -> buildings -> traffic -> meshes -> validation.

    ``season`` fixes the scenario's season (environment preset and whether
    street trees appear); ``None`` picks one from the seed.

    ``time_of_day`` is an explicit choice, never drawn from the seed (so
    every existing seed's daytime scenario is unchanged): at night the
    serializer switches on vehicle lights and the caller uses
    ``scenario_environment`` for the moonlit lighting.

    Raises
    ------
    ValueError
        If the generated scenario fails ``ScenarioValidator`` (propagated
        rather than silently producing an invalid scenario -- callers
        that want to skip-and-continue on failure should catch this).
    """
    road_gen = RoadNetworkGenerator(seed, config)
    nodes, edges = road_gen.generate(bounds)

    lanes = LaneTopologyGenerator().generate(nodes, edges)
    parking_lots = plan_parking_lots(nodes, edges, config, seed)
    buildings = BuildingPlacementGenerator(
        seed,
        config,
        tuple(BUILDING_STYLES.values()),
        keep_out_aabbs=[lot.aabb for lot in parking_lots],
    ).generate(nodes, edges)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)
    lane_connectivity = LaneConnectivityGenerator().generate(nodes, edges, lanes)
    vehicles, pedestrians = ActorPlacementGenerator(seed, config).generate(edges, traffic)
    vehicles += parked_vehicles(
        parking_lots, config, seed, max((v.vehicle_id for v in vehicles), default=-1) + 1
    )
    assign_vehicle_paint(vehicles, seed)

    # Vehicles are deliberately NOT built into box meshes here as of the
    # City Sample asset integration's Phase 1 (see KNOWN_GAPS_AND_ISSUES.md):
    # UE5 now spawns a real vehicle Blueprint asset per Vehicle.asset_path
    # instead (see scenario_serializer.py's "assets" array), not a raw
    # mesh. MeshFactory.build_vehicle_mesh itself still exists (used by
    # its own tests, and as a documented fallback shape), just no longer
    # feeds ScenarioResult.meshes. Ground truth is unaffected either way
    # -- extract_bboxes_3d_vehicles derives boxes from Vehicle's own
    # fields, not from meshes.
    #
    # Buildings are, as of this same integration effort's next phase,
    # deliberately NOT built into a flat box mesh either -- UE5 now spawns
    # real City Sample modular wall/corner/entrance pieces per building
    # instead (see building_facade.py, scenario_serializer.py's
    # "static_asset" entries). MeshFactory.build_building_mesh stays for
    # its own tests/validator coverage, same precedent as
    # build_vehicle_mesh. Ground truth is unaffected -- extract_bboxes_3d
    # derives boxes from Building.aabb/.height directly, never from mesh
    # or facade-piece geometry.
    #
    # Pedestrians, likewise, are no longer built into box meshes: UE5 now
    # spawns a real City Sample VAT pedestrian static mesh per
    # Pedestrian.asset_path instead (see scenario_serializer.py's "assets"
    # array). MeshFactory.build_pedestrian_mesh stays for its own tests
    # and as a documented fallback shape, same precedent as
    # build_vehicle_mesh. Ground truth is unaffected -- extract_bboxes_3d_
    # pedestrians derives boxes from Pedestrian's own fields, not from
    # meshes.
    meshes: List[Mesh] = [MeshFactory.build_road_mesh(lane) for lane in lanes.values()]

    building_facade_pieces: List[FacadePiece] = []
    building_palettes = draw_building_palettes(len(buildings), seed)
    building_piece_palettes: List[int] = []
    for building, palette in zip(buildings, building_palettes):
        pieces = generate_building_facade_pieces(building, BUILDING_STYLES[building.style_name])
        building_facade_pieces += pieces
        building_piece_palettes += [palette] * len(pieces)

    # One curb style and one sidewalk style per scenario, chosen from the
    # seed (an isolated stream, so it never disturbs any other generator's
    # random sequence): every tile matches, scenarios differ.
    style_rng = np.random.Generator(np.random.PCG64([seed, 0x51DE]))
    # Curbs and sidewalks are cut away where a lot's driveway crosses them,
    # and each driveway is then widened to cover the curb pieces removed.
    removed_curbs: List[Rect] = []
    road_edge_pieces = generate_road_edge_pieces(
        lanes,
        edges,
        curb_variant=int(style_rng.integers(len(DEFAULT_ROAD_EDGE_KIT.curb_asset_paths))),
        sidewalk_variant=int(style_rng.integers(len(DEFAULT_ROAD_EDGE_KIT.sidewalk_asset_paths))),
        gap_rects=[lot.driveway.gap for lot in parking_lots if lot.driveway is not None],
        removed_curbs=removed_curbs,
    )
    for lot in parking_lots:
        if lot.driveway is not None:
            lot.driveway = lot.driveway.widened(removed_curbs)
    meshes += parking_lot_meshes(parking_lots)

    # Drawn LAST from the style stream so every earlier style choice for a
    # given seed is unchanged by the season feature.
    chosen_season = season if season is not None else _draw_season(style_rng)

    lamp_style = int(style_rng.integers(len(LAMP_STYLES)))
    tree_base_style = int(style_rng.integers(len(TREE_BASE_STYLES)))
    parking_lot_props = parking_lot_pieces(parking_lots, lamp_style)
    parking_lot_props += driveway_crosswalk_pieces(parking_lots)

    street_furniture_pieces = generate_street_furniture_pieces(
        lanes,
        edges,
        lamp_style=lamp_style,
        tree_base_style=tree_base_style,
        seed=seed,
        include_trees=season_has_trees(chosen_season),
        keep_out_rects=[lot.driveway.gap for lot in parking_lots if lot.driveway is not None],
    )

    crosswalk_pieces = generate_crosswalk_pieces(nodes, edges)
    traffic_light_pieces = generate_traffic_light_pieces(lanes, edges)

    validation_report = ScenarioValidator().validate(
        bounds, nodes, edges, lanes, buildings, meshes, vehicles, pedestrians, lane_connectivity
    )
    if not validation_report.is_valid:
        raise ValueError(
            f"Scenario {scenario_id} (seed={seed}) failed validation: {validation_report.issues}"
        )

    return ScenarioResult(
        scenario_id=scenario_id,
        nodes=nodes,
        edges=edges,
        lanes=lanes,
        buildings=buildings,
        traffic=traffic,
        lane_connectivity=lane_connectivity,
        vehicles=vehicles,
        pedestrians=pedestrians,
        meshes=meshes,
        building_facade_pieces=building_facade_pieces,
        building_piece_palettes=building_piece_palettes,
        road_edge_pieces=road_edge_pieces,
        street_furniture_pieces=street_furniture_pieces,
        crosswalk_pieces=crosswalk_pieces,
        traffic_light_pieces=traffic_light_pieces,
        season=chosen_season,
        validation_report=validation_report,
        time_of_day=time_of_day,
        parking_lots=parking_lots,
        parking_lot_pieces=parking_lot_props,
        building_pieces_lit=(
            building_pieces_lit(len(building_facade_pieces), seed)
            if time_of_day == TimeOfDay.NIGHT
            else []
        ),
        building_piece_room_ids=(
            building_piece_room_ids(len(building_facade_pieces), seed)
            if time_of_day == TimeOfDay.NIGHT
            else []
        ),
    )


def default_overview_camera(bounds: Bounds, width: int = 1280, height: int = 720) -> Camera:
    """Build a camera positioned above and outside one corner of
    ``bounds``, looking down at the scenario's center -- a reasonable
    default "establishing shot" vantage point with no scenario-specific
    tuning required.

    Offset/height ratios tuned empirically (found via dogfooding: no
    rendering engine exists to eyeball actual frames against, so a
    top-down scenario plot plus this camera's own projected 2D boxes
    were compared side by side -- see KNOWN_GAPS_AND_ISSUES.md). The
    original ``0.3``/``0.6`` ratios left most of the frame empty (scene
    content filled only ~55% of image width); ``0.05``/``0.35`` fill it
    far better with no meaningful loss in visible annotations.
    """
    x_min, y_min, x_max, y_max = bounds
    center = np.array([(x_min + x_max) / 2.0, (y_min + y_max) / 2.0, 0.0])
    extent = max(x_max - x_min, y_max - y_min)

    camera_position = np.array([x_min - extent * 0.05, y_min - extent * 0.05, extent * 0.35])
    intrinsics = CameraIntrinsics.from_fov(horizontal_fov_deg=90.0, width=width, height=height)
    extrinsics = CameraExtrinsics.looking_at(camera_position, center)
    return Camera(intrinsics, extrinsics)


def render_frame(
    scenario: ScenarioResult, camera: Camera, image_id: int, file_name: str
) -> CocoFrame:
    """Project a scenario's buildings, vehicles, and pedestrians through
    ``camera`` into one COCO-ready frame.

    Each object kind's own id counter starts at 0 (``building_id``,
    ``vehicle_id``, ``pedestrian_id`` -- see their respective
    generators), so vehicles' and pedestrians' object_ids are offset by
    the preceding kinds' counts to keep the combined id space unique
    within this frame.
    """
    vehicle_id_offset = len(scenario.buildings)
    pedestrian_id_offset = vehicle_id_offset + len(scenario.vehicles)

    bboxes_3d = (
        extract_bboxes_3d(scenario.buildings)
        + extract_bboxes_3d_vehicles(scenario.vehicles, id_offset=vehicle_id_offset)
        + extract_bboxes_3d_pedestrians(scenario.pedestrians, id_offset=pedestrian_id_offset)
    )
    bboxes_3d_by_id = {bbox.object_id: bbox for bbox in bboxes_3d}
    bboxes_2d = filter_occluded(camera, project_bboxes_3d_to_2d(camera, bboxes_3d), bboxes_3d_by_id)

    return CocoFrame(
        image_id=image_id,
        file_name=file_name,
        camera=camera,
        bboxes_2d=bboxes_2d,
        bboxes_3d_by_id=bboxes_3d_by_id,
    )


def generate_dataset(
    num_scenarios: int,
    base_seed: int,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    output_dir: Path,
) -> DatasetGenerationResult:
    """Generate ``num_scenarios`` scenarios, render one overview frame
    each, and export the result as a COCO dataset plus per-scenario
    metadata files under ``output_dir``.

    Parameters
    ----------
    num_scenarios : int
        Number of scenarios to generate (seeds ``base_seed`` through
        ``base_seed + num_scenarios - 1``).
    base_seed : int
    config : ScenarioTypeConfig
    bounds : Bounds
    output_dir : Path
        Created if it doesn't exist. Writes ``annotations.json`` (COCO)
        and one ``<scenario_id>_metadata.json`` per scenario.

    Returns
    -------
    DatasetGenerationResult
    """
    start_time = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    frames: List[CocoFrame] = []
    metadata_paths: List[Path] = []

    for i in range(num_scenarios):
        frame, metadata_path = generate_and_render_one_scenario(
            index=i, base_seed=base_seed, config=config, bounds=bounds, output_dir=output_dir
        )
        frames.append(frame)
        metadata_paths.append(metadata_path)

    coco_data = export_coco(frames)
    coco_path = output_dir / "annotations.json"
    write_json(coco_path, coco_data)

    sanity_report = check_annotation_count_consistency(frames)
    elapsed_seconds = time.perf_counter() - start_time

    return DatasetGenerationResult(
        num_scenarios=num_scenarios,
        num_frames=len(frames),
        coco_path=coco_path,
        metadata_paths=metadata_paths,
        sanity_report=sanity_report,
        elapsed_seconds=elapsed_seconds,
    )


def generate_and_render_one_scenario(  # pylint: disable=too-many-arguments
    index: int, base_seed: int, config: ScenarioTypeConfig, bounds: Bounds, output_dir: Path
) -> Tuple[CocoFrame, Path]:
    """Generate scenario ``index``, render its overview frame, and write
    its metadata file -- the per-scenario body of ``generate_dataset``'s
    loop, extracted so that function's own local-variable count stays
    manageable."""
    seed = base_seed + index
    scenario_id = f"proc_scenario_{index:04d}"

    scenario = generate_scenario(seed, config, bounds, scenario_id)
    camera = default_overview_camera(bounds)
    frame = render_frame(scenario, camera, image_id=index, file_name=f"{scenario_id}.png")

    metadata = build_scenario_metadata(scenario_id, seed, config_version="1.0")
    metadata_path = output_dir / f"{scenario_id}_metadata.json"
    write_json(metadata_path, metadata.to_dict())

    return frame, metadata_path


def write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write ``data`` as JSON to ``path``."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle)


__all__ = [
    "ScenarioMetadata",
    "ScenarioResult",
    "DatasetGenerationResult",
    "generate_scenario",
    "default_overview_camera",
    "render_frame",
    "generate_dataset",
]
