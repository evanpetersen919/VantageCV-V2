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

The ``"meshes"`` array (roads, and non-hero building/pedestrian box
geometry) is produced here, alongside the ``"assets"`` array --
asset-reference + transform entries for real City Sample content. As of
Phase 1 of that integration work, vehicles are the first category
populated into ``"assets"`` (``category: "vehicle"``); props and landmark
buildings are added incrementally by later phases of the same effort.
"""

from typing import Any, Dict, List

from src.orchestration.dataset_generator import ScenarioResult
from src.procedural.actor_placement import Vehicle
from src.procedural.mesh_factory import Mesh


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


def _vehicle_to_asset_json(vehicle: Vehicle) -> Dict[str, Any]:
    """One ``Vehicle`` as an ``"assets"`` entry: asset reference +
    transform, per the City Sample integration plan's schema
    (``{"category", "asset_path", "position", "rotation_rad", "id"}``).

    ``vehicle.center`` is a 2D (x, y) ground-plane point (see
    ``ActorPlacementGenerator``); z is always 0.0 here since every
    vehicle is placed on the flat road surface.
    """
    x, y = vehicle.center
    return {
        "category": "vehicle",
        "asset_path": vehicle.asset_path,
        "position": [float(x), float(y), 0.0],
        "rotation_rad": float(vehicle.heading_rad),
        "id": vehicle.vehicle_id,
    }


def serialize_scenario(result: ScenarioResult) -> Dict[str, Any]:
    """Convert one generated scenario into the JSON-serializable dict
    :meth:`UE5Backend.load_scenario` sends as its ``"scenario"`` RPC
    parameter.

    Parameters
    ----------
    result : ScenarioResult
        A real, validated scenario from
        :func:`src.orchestration.dataset_generator.generate_scenario`.

    Returns
    -------
    Dict[str, Any]
        ``{"meshes": [...], "assets": [...]}``, safe to pass directly to
        ``json.dumps`` (see :func:`_mesh_to_json`'s docstring on why the
        numpy-to-plain-Python conversion matters) and to
        ``UE5Backend.load_scenario``.
    """
    meshes: List[Dict[str, Any]] = [_mesh_to_json(mesh) for mesh in result.meshes]
    assets: List[Dict[str, Any]] = [_vehicle_to_asset_json(v) for v in result.vehicles]
    return {"meshes": meshes, "assets": assets}
