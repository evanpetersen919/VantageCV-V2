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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from src.export.coco_exporter import CocoFrame, export_coco
from src.export.metadata_manager import ScenarioMetadata, build_scenario_metadata
from src.ground_truth.bbox_2d import project_bboxes_3d_to_2d
from src.ground_truth.bbox_3d import (
    extract_bboxes_3d,
    extract_bboxes_3d_pedestrians,
    extract_bboxes_3d_vehicles,
)
from src.procedural.actor_placement import ActorPlacementGenerator, Pedestrian, Vehicle
from src.procedural.building_placement import Building, BuildingPlacementGenerator
from src.procedural.lane_topology import Lane, LaneTopologyGenerator
from src.procedural.mesh_factory import Mesh, MeshFactory
from src.procedural.road_network import RoadEdge, RoadNetworkGenerator, RoadNode
from src.procedural.scenario import ScenarioTypeConfig
from src.procedural.traffic_network import TrafficNetwork, TrafficNetworkGenerator
from src.procedural.validator import ScenarioValidator, ValidationReport
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
    vehicles: List[Vehicle]
    pedestrians: List[Pedestrian]
    meshes: List[Mesh]
    validation_report: ValidationReport


@dataclass
class DatasetGenerationResult:
    """Summary of one full dataset generation run."""

    num_scenarios: int
    num_frames: int
    coco_path: Path
    metadata_paths: List[Path]
    sanity_report: SanityReport
    elapsed_seconds: float


def generate_scenario(
    seed: int, config: ScenarioTypeConfig, bounds: Bounds, scenario_id: str
) -> ScenarioResult:
    """Run the full Phase 1-4 procedural pipeline for one scenario:
    road network -> lanes -> buildings -> traffic -> meshes -> validation.

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
    buildings = BuildingPlacementGenerator(seed, config).generate(nodes, edges)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)
    vehicles, pedestrians = ActorPlacementGenerator(seed, config).generate(edges, traffic)

    meshes: List[Mesh] = [MeshFactory.build_road_mesh(lane) for lane in lanes.values()]
    meshes += [MeshFactory.build_building_mesh(building) for building in buildings]
    meshes += [MeshFactory.build_vehicle_mesh(vehicle) for vehicle in vehicles]
    meshes += [MeshFactory.build_pedestrian_mesh(pedestrian) for pedestrian in pedestrians]

    validation_report = ScenarioValidator().validate(
        bounds, nodes, edges, lanes, buildings, meshes, vehicles, pedestrians
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
        vehicles=vehicles,
        pedestrians=pedestrians,
        meshes=meshes,
        validation_report=validation_report,
    )


def default_overview_camera(bounds: Bounds, width: int = 1280, height: int = 720) -> Camera:
    """Build a camera positioned above and outside one corner of
    ``bounds``, looking down at the scenario's center -- a reasonable
    default "establishing shot" vantage point with no scenario-specific
    tuning required.
    """
    x_min, y_min, x_max, y_max = bounds
    center = np.array([(x_min + x_max) / 2.0, (y_min + y_max) / 2.0, 0.0])
    extent = max(x_max - x_min, y_max - y_min)

    camera_position = np.array([x_min - extent * 0.3, y_min - extent * 0.3, extent * 0.6])
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
    bboxes_2d = project_bboxes_3d_to_2d(camera, bboxes_3d)
    bboxes_3d_by_id = {bbox.object_id: bbox for bbox in bboxes_3d}

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
