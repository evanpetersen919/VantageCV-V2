"""Serialize a ``ScenarioResult`` into the plain-JSON shape
:meth:`src.ue5.backend.UE5Backend.load_scenario` sends and
``ProceduralScenarioLoader.cpp`` parses.

This module closes a real gap found while planning the City Sample asset
integration work: no committed code performed this conversion before
tonight, despite the pipeline having been verified end-to-end against a
live UE5 editor earlier in this session -- that verification ran through
an ad hoc, uncommitted scratchpad script, not through anything covered by
the test suite or reusable by future phases. See
KNOWN_GAPS_AND_ISSUES.md.

The ``"meshes"`` array (roads and pedestrian box geometry) is produced here,
alongside the ``"assets"`` array -- asset-reference + transform entries for
real City Sample content. Vehicles (``category: "vehicle"``, Phase 1) and
building facade pieces (``category: "static_asset"``, the next phase of the
same effort -- real modular wall/corner/entrance meshes tiled per building,
see ``building_facade.py``) both populate ``"assets"``; street props are a
deliberate later fast-follow, not part of this effort yet.
"""

from typing import Any, Dict, List, Optional

from src.orchestration.dataset_generator import ScenarioResult
from src.procedural.actor_placement import Vehicle
from src.procedural.block_pavement import build_block_pavement_meshes
from src.procedural.building_facade import FacadePiece
from src.procedural.city_sample_assets import VEHICLE_PART_PATHS
from src.procedural.environment import EnvironmentConfig, build_ground_mesh
from src.procedural.mesh_factory import Mesh
from src.procedural.roofs import build_roof_meshes


def _mesh_to_json(mesh: Mesh) -> Dict[str, Any]:
    """One ``Mesh`` as the JSON shape ``ProceduralScenarioLoader.cpp``'s
    ``ParseMeshData`` expects: ``vertices``/``uvs`` as nested coordinate
    lists, ``triangles`` as a flat int list, ``material`` as a string.

    ``.tolist()`` converts numpy arrays (and their ``numpy.float64``/
    ``numpy.int64`` elements) into plain Python ``float``/``int`` --
    without it, ``json.dumps`` raises ``TypeError`` on the numpy scalar
    types every ``Mesh`` field actually holds.
    """
    return {
        "vertices": mesh.vertices.tolist(),
        "triangles": mesh.triangles.tolist(),
        "uvs": mesh.uvs.tolist(),
        "material": mesh.material,
    }


def _vehicle_folder_name(asset_path: str) -> str:
    """Extract the vehicle folder name (e.g. ``"vehCar_vehicle02"``) from
    a real City Sample asset path of the form
    ``"/Game/Vehicle/<folder>/Mesh/..."`` -- the path segment
    ``VEHICLE_PART_PATHS`` is keyed by.
    """
    parts = asset_path.split("/")
    # ["", "Game", "Vehicle", "<folder>", "Mesh", ...] -- index 3.
    return parts[3] if len(parts) > 3 else ""


def _vehicle_to_asset_json(vehicle: Vehicle) -> Dict[str, Any]:
    """One ``Vehicle`` as an ``"assets"`` entry: asset reference +
    transform, per the City Sample integration plan's schema
    (``{"category", "asset_path", "position", "rotation_rad", "id"}``),
    plus ``"part_paths"`` -- the same vehicle's real wheel/door/glass/
    interior static meshes (see ``city_sample_assets.py``'s
    ``VEHICLE_PART_PATHS`` for why these need no per-part offset), spawned
    alongside the body at the exact same position/rotation. A vehicle
    folder with no ``VEHICLE_PART_PATHS`` entry gets an empty list here,
    not an error -- see that module's own docstring.

    ``vehicle.center`` is a 2D (x, y) ground-plane point (see
    ``ActorPlacementGenerator``); z is always 0.0 here since every
    vehicle is placed on the flat road surface.
    """
    x, y = vehicle.center
    folder = _vehicle_folder_name(vehicle.asset_path)
    return {
        "category": "vehicle",
        "asset_path": vehicle.asset_path,
        "part_paths": VEHICLE_PART_PATHS.get(folder, []),
        "position": [float(x), float(y), 0.0],
        "rotation_rad": float(vehicle.heading_rad),
        "id": vehicle.vehicle_id,
    }


def _facade_piece_to_asset_json(piece: FacadePiece, piece_id: int) -> Dict[str, Any]:
    """One ``FacadePiece`` (a real City Sample wall/corner/entrance static
    mesh) as an ``"assets"`` entry: ``category: "static_asset"``, no
    ``part_paths`` -- unlike a vehicle, each facade piece is its own
    independent spawn, not a body with attached sub-parts.
    ``ProceduralScenarioLoader.cpp`` routes any recognized category
    (``"vehicle"`` or ``"static_asset"``) through the same
    ``UVehicleActorSpawner::SpawnVehicle``, which already handles an
    empty ``PartPaths`` list gracefully.
    """
    x, y, z = piece.position
    entry: Dict[str, Any] = {
        "category": "static_asset",
        "asset_path": piece.asset_path,
        "part_paths": [],
        "position": [float(x), float(y), float(z)],
        "rotation_rad": float(piece.rotation_rad),
        "id": piece_id,
    }
    if piece.scale is not None:
        # Per-instance scale along the mesh's own local axes (a negative
        # component mirrors it); omitted when unscaled so existing
        # payloads stay byte-identical.
        entry["scale"] = [float(component) for component in piece.scale]
    return entry


def serialize_scenario(
    result: ScenarioResult, environment: Optional[EnvironmentConfig] = None
) -> Dict[str, Any]:
    """Convert one generated scenario into the JSON-serializable dict
    :meth:`UE5Backend.load_scenario` sends as its ``"scenario"`` RPC
    parameter.

    Parameters
    ----------
    result : ScenarioResult
        A real, validated scenario from
        :func:`src.orchestration.dataset_generator.generate_scenario`.
    environment : Optional[EnvironmentConfig]
        When given, a ground plane, the sidewalk-height block paving and
        the buildings' flat roof slabs are appended to ``"meshes"`` and an
        ``"environment"`` object (sun, fog, grade, hide-template-terrain)
        is added for the UE5 plugin to apply. ``None`` (the default)
        serializes only the scenario itself.

    Returns
    -------
    Dict[str, Any]
        ``{"meshes": [...], "assets": [...]}`` (plus ``"environment"``
        when one was given), safe to pass directly to
        ``json.dumps`` (see :func:`_mesh_to_json`'s docstring on why the
        numpy-to-plain-Python conversion matters) and to
        ``UE5Backend.load_scenario``.
    """
    meshes: List[Dict[str, Any]] = [_mesh_to_json(mesh) for mesh in result.meshes]
    assets: List[Dict[str, Any]] = [_vehicle_to_asset_json(v) for v in result.vehicles]
    assets += [
        _facade_piece_to_asset_json(piece, piece_id)
        for piece_id, piece in enumerate(result.building_facade_pieces)
    ]
    # Curbs and sidewalks: same "static_asset" entries, ids continuing
    # after the facade pieces so every asset id stays unique.
    id_offset = len(result.building_facade_pieces)
    assets += [
        _facade_piece_to_asset_json(piece, id_offset + piece_id)
        for piece_id, piece in enumerate(result.road_edge_pieces)
    ]
    payload: Dict[str, Any] = {"meshes": meshes, "assets": assets}
    if environment is not None:
        meshes.append(_mesh_to_json(build_ground_mesh(environment)))
        meshes += [
            _mesh_to_json(mesh) for mesh in build_block_pavement_meshes(result.nodes, result.edges)
        ]
        meshes += [_mesh_to_json(mesh) for mesh in build_roof_meshes(result.buildings)]
        payload["environment"] = environment.to_json()
    return payload
