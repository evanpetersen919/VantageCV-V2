"""Full-scene semantic classes, on Cityscapes label ids, and what every scene part maps to.

Ids and colours are the Cityscapes ``labelIds`` and palette, so standard tooling reads the maps:
only the subset this generator produces is used. Every asset path and procedural surface the
generator can emit is mapped here by rule (the rules were written from the full inventory of
scenario assets, see ``LICENSING.md`` and ``tests/unit/test_semantic_classes.py``, which fails if
a new asset appears that no rule covers).

Choices where Cityscapes is ambiguous, all documented in the dataset card: curbs and tree-pit
grates are ``sidewalk``; parking meters, hydrants, parking blocks and bins are ``static``; a
road sign is ``traffic sign`` including its post; lamp posts are ``pole``; roof equipment is part
of ``building``; trailers are ``truck`` (as in the instance annotations); the painted hood of the
ego car is ``ego vehicle``; sky is wherever the engine reports no surface.
"""

from typing import Dict, List, Tuple

UNLABELED = 0
EGO_VEHICLE = 1
STATIC = 4
ROAD = 7
SIDEWALK = 8
BUILDING = 11
POLE = 17
TRAFFIC_LIGHT = 19
TRAFFIC_SIGN = 20
VEGETATION = 21
TERRAIN = 22
SKY = 23
PERSON = 24
CAR = 26
TRUCK = 27
BUS = 28

CLASS_NAMES: Dict[int, str] = {
    UNLABELED: "unlabeled",
    EGO_VEHICLE: "ego vehicle",
    STATIC: "static",
    ROAD: "road",
    SIDEWALK: "sidewalk",
    BUILDING: "building",
    POLE: "pole",
    TRAFFIC_LIGHT: "traffic light",
    TRAFFIC_SIGN: "traffic sign",
    VEGETATION: "vegetation",
    TERRAIN: "terrain",
    SKY: "sky",
    PERSON: "person",
    CAR: "car",
    TRUCK: "truck",
    BUS: "bus",
}

PALETTE: Dict[int, Tuple[int, int, int]] = {
    UNLABELED: (0, 0, 0),
    EGO_VEHICLE: (0, 0, 0),
    STATIC: (111, 74, 0),
    ROAD: (128, 64, 128),
    SIDEWALK: (244, 35, 232),
    BUILDING: (70, 70, 70),
    POLE: (153, 153, 153),
    TRAFFIC_LIGHT: (250, 170, 30),
    TRAFFIC_SIGN: (220, 220, 0),
    VEGETATION: (107, 142, 35),
    TERRAIN: (152, 251, 152),
    SKY: (70, 130, 180),
    PERSON: (220, 20, 60),
    CAR: (0, 0, 142),
    TRUCK: (0, 0, 70),
    BUS: (0, 60, 100),
}

# Where two groups meet at the same depth, the earlier class here wins.
PRIORITY: List[int] = [
    PERSON,
    CAR,
    TRUCK,
    BUS,
    TRAFFIC_LIGHT,
    TRAFFIC_SIGN,
    POLE,
    VEGETATION,
    STATIC,
    BUILDING,
    SIDEWALK,
    ROAD,
    TERRAIN,
]

# The class of a vehicle by its type, the same split as the instance annotations (pickups and vans
# are cars there, whatever their asset folder is called).
VEHICLE_TYPE_CLASS: Dict[str, int] = {"sedan": CAR, "suv": CAR, "truck": TRUCK, "bus": BUS}

# (substring of the asset path, class), first match wins.
_ASSET_RULES: List[Tuple[str, int]] = [
    ("/Game/Building/", BUILDING),
    ("/Game/VantageCV/NightGlass", BUILDING),
    ("/Game/Vehicle/vehBus_", BUS),
    ("/Game/Vehicle/vehTruck_", TRUCK),
    ("/Game/Vehicle/vehCar_", CAR),
    ("/Game/Vehicle/vehVan_", CAR),
    ("/Game/VehicleVarietyVol2/", TRUCK),
    ("/Game/VantageCV/Pedestrians/", PERSON),
    ("/Game/Crowd/", PERSON),
    ("/Game/Road/Kit_Sidewalk_A/", SIDEWALK),
    ("/Game/Road/Kit_MeshDecals_A/", ROAD),
    ("/Game/Megascans/3D_Assets/Modular_Curb", SIDEWALK),
    ("/Game/Megascans/3D_Assets/No_Parking_Road_Sign", TRAFFIC_SIGN),
    ("/Game/Megascans/3D_Assets/Fire_Hydrant", STATIC),
    ("/Game/Megascans/3D_Assets/Parking_Block", STATIC),
    ("/Game/Megascans/3D_Assets/Parking_Meter", STATIC),
    ("/Game/Prop/Kit_StreetLamp_A/Mesh/SM_StreetLamp_A_StopLight", TRAFFIC_LIGHT),
    ("/Game/Prop/Kit_StreetLamp_", POLE),
    ("/Game/Prop/Kit_Trashcan", STATIC),
    ("/Game/Prop/Kit_TreeBase", SIDEWALK),
    ("/Game/Prop/Kit_Tree_", VEGETATION),
    ("/Game/Prop/Kit_roof_", BUILDING),
    ("/Game/Prop/Kit_Roof_", BUILDING),
]


def asset_class(asset_path: str) -> int:
    """The class of a placed asset, ``UNLABELED`` when no rule covers it."""
    for fragment, class_id in _ASSET_RULES:
        if fragment in asset_path:
            return class_id
    return UNLABELED


def mesh_class(material: str) -> int:
    """The class of a procedural surface from its material name, ``UNLABELED`` when unknown."""
    if material in ("asphalt", "paint_white", "paint_yellow"):
        return ROAD
    if material.startswith("pavement"):
        return SIDEWALK
    if material == "ground":
        return TERRAIN
    if material.startswith("roof"):
        return BUILDING
    return UNLABELED
