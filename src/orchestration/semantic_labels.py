"""Full-scene class map and depth map for a frame, from what the game renders.

One ``CaptureObjectMasks`` request carries the scene's parts grouped by class, in priority order
(``semantic_classes.PRIORITY``). The game renders the scene's depth once and each group alone;
a pixel takes the class of the group whose own depth equals the scene depth there (nothing nearer
hides it), the earlier group winning a tie. Pixels with no surface are sky; pixels under the
painted hood are the ego vehicle. The same call returns the scene depth, which is saved as a
second annotation.

Depth file: 16-bit PNG, value = metres * ``DEPTH_SCALE`` (so 1/256 m resolution, 0 to about
256 m), measured along the camera's viewing axis; 0 marks no surface (sky) and the hood.
"""

import dataclasses
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt
from PIL import Image

from src.ground_truth.semantic_classes import (
    EGO_VEHICLE,
    PALETTE,
    PRIORITY,
    SKY,
    UNLABELED,
    VEHICLE_TYPE_CLASS,
    asset_class,
    mesh_class,
)
from src.orchestration.hood import hood_mask
from src.orchestration.live_render import vertical_fov_deg
from src.orchestration.scenario_serializer import object_asset_indices
from src.procedural.night_lights import vehicle_glows

DEPTH_SCALE = 256.0
NO_SURFACE_CM = 1.0e7  # the engine's depth is at least this where nothing is drawn
Groups = List[Tuple[int, Dict[str, List[int]]]]


@dataclasses.dataclass
class SemanticMaps:
    """A frame's class map (Cityscapes label ids) and depth in metres (0 = no surface)."""

    classes: npt.NDArray[np.uint8]
    depth_m: npt.NDArray[np.float32]


def _vehicle_overrides(
    scenario: Any, payload: Dict[str, Any]
) -> Tuple[Dict[int, int], Dict[int, int]]:
    """(asset index -> class, glow index -> class) from the scenario's vehicle types.

    The path of a pickup or van says "truck" or "van", but the annotations call them cars; the
    class map follows the annotations. A tractor-trailer's trailer takes its tractor's class,
    and every lamp glow takes its vehicle's.
    """
    members = object_asset_indices(scenario, payload)
    offset = len(scenario.buildings)
    assets: Dict[int, int] = {}
    for vehicle in scenario.vehicles:
        class_id = VEHICLE_TYPE_CLASS.get(vehicle.vehicle_type)
        if class_id is None:
            continue
        for index in members.get(vehicle.vehicle_id + offset, []):
            assets[index] = class_id
    glows: Dict[int, int] = {}
    position = 0
    for vehicle in scenario.vehicles:
        for _ in vehicle_glows(vehicle):
            class_id = VEHICLE_TYPE_CLASS.get(vehicle.vehicle_type)
            if class_id is not None:
                glows[position] = class_id
            position += 1
    return assets, glows


def class_groups(payload: Dict[str, Any], scenario: Any = None) -> Groups:
    """The payload's assets, procedural meshes and lamp glows grouped by class, in priority order.

    With the ``scenario`` the payload was made from, vehicles take the class of their type.
    """
    by_class: Dict[int, Dict[str, List[int]]] = {}

    def group(class_id: int) -> Dict[str, List[int]]:
        return by_class.setdefault(class_id, {"assets": [], "meshes": [], "glows": []})

    vehicle_assets, vehicle_glow_classes = (
        _vehicle_overrides(scenario, payload) if scenario is not None else ({}, {})
    )
    for index, asset in enumerate(payload["assets"]):
        class_id = vehicle_assets.get(index, asset_class(asset["asset_path"]))
        if class_id != UNLABELED:
            group(class_id)["assets"].append(index)
    for index, mesh in enumerate(payload.get("meshes", [])):
        class_id = mesh_class(mesh["material"])
        if class_id != UNLABELED:
            group(class_id)["meshes"].append(index)
    for index, class_id in vehicle_glow_classes.items():
        group(class_id)["glows"].append(index)
    return [(class_id, by_class[class_id]) for class_id in PRIORITY if class_id in by_class]


def unmapped_parts(payload: Dict[str, Any]) -> List[str]:
    """Asset paths and mesh materials no class rule covers (they would be labelled unlabeled)."""
    missing = {
        asset["asset_path"] for asset in payload["assets"] if asset_class(asset["asset_path"]) == 0
    }
    missing |= {
        "mesh:" + mesh["material"]
        for mesh in payload.get("meshes", [])
        if mesh_class(mesh["material"]) == 0
    }
    return sorted(missing)


async def capture_semantic(  # pylint: disable=too-many-locals
    backend: Any,
    groups: Groups,
    size: Tuple[int, int],
    scratch: Path,
    hood_row: Optional[int] = None,
) -> SemanticMaps:
    """Ask the game for the class and depth maps of the frame it is currently showing."""
    scratch.parent.mkdir(parents=True, exist_ok=True)
    visible_path = scratch.with_suffix(".u16")
    depth_path = scratch.with_suffix(".f32")
    reply = await backend.call(
        "CaptureObjectMasks",
        {
            "out_path": str(visible_path.resolve()),
            "depth_path": str(depth_path.resolve()),
            "objects": [group for _, group in groups],
            "width": size[0],
            "height": size[1],
            "vertical_fov_deg": vertical_fov_deg(),
        },
    )
    shape = (reply["height"], reply["width"])
    visible = np.fromfile(visible_path, dtype="<u2").reshape(shape)
    depth_cm = np.fromfile(depth_path, dtype="<f4").reshape(shape)
    visible_path.unlink(missing_ok=True)
    depth_path.unlink(missing_ok=True)

    classes = np.zeros(shape, dtype=np.uint8)
    for index, (class_id, _) in enumerate(groups):
        classes[visible == index + 1] = class_id
    no_surface = depth_cm >= NO_SURFACE_CM
    classes[no_surface & (classes == UNLABELED)] = SKY
    depth_m = np.where(no_surface, 0.0, depth_cm / 100.0).astype(np.float32)
    if hood_row is not None:
        covered = hood_mask(hood_row, (shape[1], shape[0]))
        classes[covered] = EGO_VEHICLE
        depth_m[covered] = 0.0
    return SemanticMaps(classes, depth_m)


def save_maps(maps: SemanticMaps, directory: Path, name: str) -> Tuple[str, str]:
    """Write ``semantic/<name>.png`` (class ids) and ``depth/<name>.png`` (16-bit, see module)."""
    semantic_dir, depth_dir = directory / "semantic", directory / "depth"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    depth_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(maps.classes, mode="L").save(semantic_dir / f"{name}.png")
    scaled = np.clip(np.rint(maps.depth_m * DEPTH_SCALE), 0, 65535).astype(np.uint16)
    Image.fromarray(scaled).save(depth_dir / f"{name}.png")
    return f"semantic/{name}.png", f"depth/{name}.png"


def colorize(classes: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
    """An RGB picture of a class map in the Cityscapes palette (for checking by eye)."""
    picture = np.zeros(classes.shape + (3,), dtype=np.uint8)
    for class_id, colour in PALETTE.items():
        picture[classes == class_id] = colour
    return picture
