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

The ``"meshes"`` array (roads and other flat procedural geometry) is
produced here, alongside the ``"assets"`` array -- asset-reference +
transform entries for real City Sample content. Vehicles (``category:
"vehicle"``), building facade pieces, and pedestrians (``category:
"static_asset"`` for both -- see ``building_facade.py``/
``city_sample_assets.py``'s ``PEDESTRIAN_BODY_ASSET_PATHS``) all
populate ``"assets"``.
"""

from typing import Any, Dict, List, Optional

from src.orchestration.dataset_generator import ScenarioResult
from src.procedural.actor_placement import Pedestrian, Vehicle
from src.procedural.block_pavement import build_block_pavement_meshes
from src.procedural.building_facade import FacadePiece
from src.procedural.city_sample_assets import PEDESTRIAN_MESH_FORWARD_OFFSET_RAD, VEHICLE_PART_PATHS
from src.procedural.environment import EnvironmentConfig, TimeOfDay, build_ground_mesh
from src.procedural.intersection_pavement import build_intersection_pavement_meshes
from src.procedural.mesh_factory import Mesh
from src.procedural.night_lights import vehicle_lights
from src.procedural.roofs import build_roof_meshes, generate_roof_prop_pieces
from src.procedural.street_furniture import LAMP_ASSET_PATHS, STREET_LAMP_OFF_OVERRIDES


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


def _pedestrian_to_asset_json(
    pedestrian: Pedestrian, piece_id: int, enable_live_pose_preview: bool = False
) -> Dict[str, Any]:
    """One ``Pedestrian`` as an ``"assets"`` entry: ``category:
    "static_asset"``. ``part_paths`` carries this pedestrian's own real,
    independently-sampled top/bottom/shoe/face combination (see
    ``city_sample_assets.py``'s ``PEDESTRIAN_TOP_ASSET_PATHS`` and
    siblings), spawned as sibling static mesh components at zero
    relative offset -- confirmed live to assemble correctly, the same
    mechanism a vehicle's wheels/doors already use, unlike a facade
    piece (which never has parts).

    ``pedestrian.center`` is a 2D (x, y) ground-plane point (see
    ``ActorPlacementGenerator``); z is ``pedestrian.surface_z`` -- either
    the real sidewalk height or the real road surface height (matching a
    vehicle's own 0.0), depending on how this pedestrian was placed (see
    ``Pedestrian.surface_z``'s own docstring for the real floating-on-
    the-road bug this fixes). This mesh's own pivot sits at its feet
    (confirmed via ``GetStaticMeshBounds``: both migrated meshes'
    vertical extent starts at ~0), so ``surface_z`` is exactly the height
    its feet need to be at.

    ``rotation_rad`` adds ``PEDESTRIAN_MESH_FORWARD_OFFSET_RAD`` on top
    of ``pedestrian.heading_rad`` -- a real, live-verified correction for
    this specific mesh's own forward-axis authoring convention (see that
    constant's own docstring); ``heading_rad`` itself stays the pedestrian's
    true physical direction of travel for ground truth, unaffected by
    this rendering-only correction.

    ``material_scalar_overrides`` carries ``pedestrian.pose_frame`` as
    the real VAT material's ``"Frame"`` parameter (see
    ``city_sample_assets.py``'s ``PEDESTRIAN_WALKING_CLIP``/
    ``PEDESTRIAN_STANDING_CLIP``) -- ``ProceduralScenarioLoader.cpp``
    applies it to the body AND every part component identically, so a
    pedestrian's whole outfit freezes at the same one real, distinct
    baked pose instead of every pedestrian defaulting to the exact same
    frame.

    Real root cause of an earlier bug where pedestrians visibly kept
    walking regardless of this override (see KNOWN_GAPS_AND_ISSUES.md):
    ``ML_BoneAnimation``'s ``GetFrame`` function gates pose selection on
    a static switch, ``Animate`` -- when true it drives the pose from
    real elapsed wall-clock time instead of this "Frame" value at all.
    Fixed at the content level (every real character/outfit material
    instance's own ``Animate`` override corrected to ``false``), not
    here -- no scalar override on this path can influence a static
    switch.

    ``enable_live_pose_preview``, when true, adds
    ``"enable_live_pose_preview": true`` to this entry -- an opt-in,
    interactive-QA-only flag (see ``FScenarioAssetData::
    bEnableLivePosePreview``'s own comment) that makes this pedestrian
    animate continuously in real time instead of staying frozen at
    ``pose_frame``. Deliberately never set by the real dataset-
    generation pipeline (``generate_scenario`` callers never pass this
    through): a scenario's captured pose must be a deterministic
    function of its seed for the dataset to be reproducible, which
    real-time animation would break. Absent (not ``false``) when
    disabled, matching every other optional field in this schema.
    """
    x, y = pedestrian.center
    asset: Dict[str, Any] = {
        "category": "static_asset",
        "asset_path": pedestrian.asset_path,
        "part_paths": pedestrian.part_paths,
        "position": [float(x), float(y), pedestrian.surface_z],
        "rotation_rad": float(pedestrian.heading_rad) + PEDESTRIAN_MESH_FORWARD_OFFSET_RAD,
        "material_scalar_overrides": {"Frame": pedestrian.pose_frame},
        "id": piece_id,
    }
    if enable_live_pose_preview:
        asset["enable_live_pose_preview"] = True
    return asset


def _facade_piece_to_asset_json(
    piece: FacadePiece,
    piece_id: int,
    material_scalar_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
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
    if material_scalar_overrides:
        entry["material_scalar_overrides"] = dict(material_scalar_overrides)
    return entry


def _street_lamp_overrides(piece: FacadePiece) -> Optional[Dict[str, float]]:
    """The daytime "lamp off" override for a regular street lamp, else
    ``None`` (trees, hydrants, signs etc. are untouched)."""
    return STREET_LAMP_OFF_OVERRIDES if piece.asset_path in LAMP_ASSET_PATHS else None


def serialize_scenario(
    result: ScenarioResult,
    environment: Optional[EnvironmentConfig] = None,
    enable_live_pose_preview: bool = False,
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
        When given, a ground plane, the sidewalk-height block paving, a
        paved intersection surface at every node and the buildings' flat
        roof slabs are appended to ``"meshes"`` and an
        ``"environment"`` object (sun, fog, grade, hide-template-terrain)
        is added for the UE5 plugin to apply. ``None`` (the default)
        serializes only the scenario itself.
    enable_live_pose_preview : bool
        When true, every pedestrian asset entry gets a real, continuous,
        wall-clock-time-driven walk-cycle animation in the UE5 preview
        instead of a frozen ``pose_frame`` -- an interactive QA/review
        aid only (see :func:`_pedestrian_to_asset_json`'s own docstring
        for why this must stay opt-in). The real dataset-generation
        pipeline never passes ``True`` here: a scenario's captured pose
        must be a deterministic function of its seed to keep the
        dataset reproducible.

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
    night = result.time_of_day == TimeOfDay.NIGHT
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
    id_offset += len(result.road_edge_pieces)
    assets += [
        _facade_piece_to_asset_json(
            piece,
            id_offset + piece_id,
            None if night else _street_lamp_overrides(piece),
        )
        for piece_id, piece in enumerate(result.street_furniture_pieces)
    ]
    id_offset += len(result.street_furniture_pieces)
    assets += [
        _facade_piece_to_asset_json(piece, id_offset + piece_id)
        for piece_id, piece in enumerate(result.crosswalk_pieces)
    ]
    id_offset += len(result.crosswalk_pieces)
    assets += [
        _facade_piece_to_asset_json(piece, id_offset + piece_id)
        for piece_id, piece in enumerate(result.traffic_light_pieces)
    ]
    id_offset += len(result.traffic_light_pieces)
    assets += [
        _pedestrian_to_asset_json(pedestrian, id_offset + piece_id, enable_live_pose_preview)
        for piece_id, pedestrian in enumerate(result.pedestrians)
    ]
    payload: Dict[str, Any] = {"meshes": meshes, "assets": assets}
    if night:
        # Real light actors (see night_lights.py): a daytime payload
        # carries no "lights" key at all.
        payload["lights"] = [
            light.to_json() for vehicle in result.vehicles for light in vehicle_lights(vehicle)
        ]
    if environment is not None:
        meshes.append(_mesh_to_json(build_ground_mesh(environment)))
        meshes += [
            _mesh_to_json(mesh) for mesh in build_block_pavement_meshes(result.nodes, result.edges)
        ]
        meshes += [
            _mesh_to_json(mesh)
            for mesh in build_intersection_pavement_meshes(result.nodes, result.edges)
        ]
        meshes += [_mesh_to_json(mesh) for mesh in build_roof_meshes(result.buildings)]
        # Rooftop equipment goes with the roofs: only when dressing the scene.
        id_offset += len(result.pedestrians)
        assets += [
            _facade_piece_to_asset_json(piece, id_offset + piece_id)
            for piece_id, piece in enumerate(generate_roof_prop_pieces(result.buildings))
        ]
        payload["environment"] = environment.to_json()
    return payload
