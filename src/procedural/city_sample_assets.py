"""Real City Sample asset paths for objects this project places
procedurally but no longer builds raw box geometry for -- vehicles as of
Phase 1 of the City Sample asset integration
(``feature/city-sample-asset-integration``); props and Hero landmark
buildings in later phases of that same effort.

These are each vehicle's static body-shell mesh (``SM_Frame_<vehicle
folder>``), not the ``BP_veh*_Sandbox`` driveable-vehicle Blueprints
City Sample itself uses, and not that vehicle's combined skeletal rig
either. Both alternatives were tried first and real-screenshot-confirmed
broken (see KNOWN_GAPS_AND_ISSUES.md for the full investigation):

1. The ``_Sandbox`` Blueprints' parent chain ultimately depends on
   ``ACitySampleVehicleBase`` -- a native C++ class defined in
   CitySample's own game-project *source*
   (``Source/CitySample/Vehicles/CitySampleVehicleBase.h``), not
   portable content, and itself deeply wired into CitySample's gameplay
   framework (Mass AI traffic control, Enhanced Input, a custom UI/menu
   system, photo mode, ``ACitySampleCharacter``) that this project has
   no use for.
2. Each vehicle's combined skeletal mesh (``SKM_<folder>``) loaded and
   spawned without error, with correct position/valid mesh bounds -- but
   a real live screenshot showed it rendering as only a tiny sliver of
   its true geometry. City Sample's skeletal rigs drive a runtime
   damage-state system (Sandbox/Destruction/Deformable); without an
   AnimBlueprint actively posing them, the reference pose alone doesn't
   show the intact body.

``SM_Frame_<folder>`` -- a plain static mesh with no skeleton at all --
has no such pose dependency and renders its authored geometry
unconditionally; confirmed present for all 14 vehicles (unlike the
skeletal ``SKM_Exterior_<folder>`` variant only some vehicles have,
which would have required two different code paths).

``VEHICLE_PART_PATHS`` (wheels/doors) closes the "body shell only" gap
flagged above. Confirmed via a real live test (spawning each part at
the same position/rotation as the body, no offset): City Sample's
wheel/door static meshes are pre-modeled in their final assembled
position already (a common modular-vehicle-kit convention -- each
part's own vertex data already encodes where it sits relative to the
vehicle's shared origin), so no per-part attachment offset/socket needs
computing at all -- confirmed correct via a real screenshot showing a
fully assembled car (wheels at all four corners, a correctly placed
door with handle) built entirely from identity-transform parts. Part
counts genuinely differ per vehicle (checked all 14 folders directly,
not assumed uniform): most have 4 wheels (front/rear, L/R) + 2 front
doors; the two dual-rear-axle trucks (vehicle08/11) have 6 wheels (an
extra "Axel3" pair) + 2 doors; the trailer has 6 wheels across 3 axles
and no doors (no cab); the bus has 4 wheels and no doors (modeled
differently, not as simple hinged front doors).

Paths point at where these assets need to be migrated to inside
``VantageCV_UE5``'s own ``Content/`` (Epic's Migrate tool, from the
``CitySample`` project) before they resolve to anything in-editor --
this module only defines *which* assets each vehicle type should
resolve to, not the migration itself (a manual, per-phase step; see the
integration plan).

Body-type classification caveat: City Sample's "Car" folders don't
distinguish sedan vs. SUV by name -- the split below is a reasonable,
deliberately-flagged-as-unverified assignment (not a visual
classification), giving both categories real variety consistent with
``vehicle_mix``'s own weighting (sedan is the dominant category in
every scenario template).
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Keys must match ActorPlacementGenerator's own VEHICLE_DIMENSIONS keys
# exactly (sedan/suv/truck/bus) -- see actor_placement.py and every
# scenario_templates/*.yaml's vehicle_mix block. City Sample has no
# distinct "van" category; the two van models are folded into "suv"
# (closer in size/role to a passenger SUV than to a cargo truck).
VEHICLE_ASSET_PATHS: Dict[str, List[str]] = {
    "sedan": [
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Frame_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Frame_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Frame_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Frame_vehCar_vehicle07",
    ],
    "suv": [
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Frame_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Frame_vehCar_vehicle13",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Frame_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Frame_vehVan_vehicle09",
    ],
    "truck": [
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Frame_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Frame_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Frame_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SM_Frame_vehTruck_trailer01",
    ],
    "bus": [
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Frame_vehBus_vehicle10",
    ],
}

# Additional static meshes (wheels/doors) spawned alongside a vehicle's
# body at the exact same position/rotation -- see this module's own
# docstring for why no per-part offset is needed. Keyed by vehicle
# folder name (the path segment shared by every asset under one
# vehicle, e.g. "vehCar_vehicle02"), not by body-type category, since
# every vehicle's part list is genuinely its own. A vehicle whose body
# path isn't a key here (there are none currently, but this isn't
# statically guaranteed) simply gets no extra parts -- see
# scenario_serializer.py's real fallback for that case.
VEHICLE_PART_PATHS: Dict[str, List[str]] = {
    "vehCar_vehicle02": [
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Wheel_Front_L_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Wheel_Front_R_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Wheel_Rear_L_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Wheel_Rear_R_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Door_Front_L_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Door_Front_R_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/Transparent/SM_All_Trans_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_Interior_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Headlight_L_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Headlight_R_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Taillight_L_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Taillight_R_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Steering_Wheel_vehCar_vehicle02",
    ],
    # No headlight/taillight meshes exist for this vehicle -- an earlier
    # survey pass wrongly claimed they did (confirmed the error via
    # real live spawn failures: "failed to load static mesh" for all
    # four paths, then confirmed on disk that they genuinely don't
    # exist). Always trust a live spawn failure over an earlier survey.
    "vehCar_vehicle03": [
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Wheel_Front_L_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Wheel_Front_R_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Wheel_Rear_L_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Wheel_Rear_R_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Door_Front_L_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Door_Front_R_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/Transparent/SM_All_Trans_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Frame_Interior_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Steering_Wheel_vehCar_vehicle03",
    ],
    "vehCar_vehicle05": [
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Wheel_Front_L_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Wheel_Front_R_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Wheel_Rear_L_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Wheel_Rear_R_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Door_Front_L_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Door_Front_R_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/Transparent/SM_All_Trans_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Frame_Interior_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Headlight_L_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Headlight_R_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Taillight_L_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Taillight_R_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SM_Steering_Wheel_vehCar_vehicle05",
    ],
    "vehCar_vehicle06": [
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Wheel_Front_L_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Wheel_Front_R_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Wheel_Rear_L_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Wheel_Rear_R_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Door_Front_L_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Door_Front_R_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/Transparent/SM_All_Trans_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Frame_Interior_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Headlight_L_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Headlight_R_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Taillight_L_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Taillight_R_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Steering_Wheel_vehCar_vehicle06",
    ],
    "vehCar_vehicle07": [
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Wheel_Front_L_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Wheel_Front_R_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Wheel_Rear_L_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Wheel_Rear_R_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Door_Front_L_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Door_Front_R_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/Transparent/SM_All_Trans_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Frame_Interior_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Headlight_L_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Headlight_R_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Taillight_L_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Taillight_R_vehCar_vehicle07",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SM_Steering_Wheel_vehCar_vehicle07",
    ],
    "vehCar_vehicle12": [
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Wheel_Front_L_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Wheel_Front_R_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Wheel_Rear_L_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Wheel_Rear_R_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Door_Front_L_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Door_Front_R_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/Transparent/SM_All_Trans_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Frame_Interior_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Steering_Wheel_vehCar_vehicle12",
    ],
    # No headlight/taillight meshes exist for this vehicle -- confirmed
    # by direct folder inspection, not an oversight.
    "vehCar_vehicle13": [
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Wheel_Front_L_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Wheel_Front_R_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Wheel_Rear_L_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Wheel_Rear_R_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Door_Front_L_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Door_Front_R_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/Transparent/SM_All_Trans_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Frame_Interior_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Headlight_L_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Headlight_R_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Taillight_L_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Taillight_R_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Steering_Wheel_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Turn_Signal_L_vehCar_vehicle13",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Turn_Signal_R_vehCar_vehicle13",
    ],
    "vehVan_vehicle01": [
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Wheel_Front_L_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Wheel_Front_R_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Wheel_Rear_L_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Wheel_Rear_R_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Door_Front_L_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Door_Front_R_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/Transparent/SM_All_Trans_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Frame_Interior_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Headlight_L_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Headlight_R_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Taillight_L_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Taillight_R_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Steering_Wheel_vehVan_vehicle01",
    ],
    # No headlight/taillight meshes exist for this vehicle -- confirmed
    # by direct folder inspection.
    "vehVan_vehicle09": [
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Wheel_Front_L_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Wheel_Front_R_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Wheel_Rear_L_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Wheel_Rear_R_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Door_Front_L_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Door_Front_R_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/Transparent/SM_All_Trans_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Frame_Interior_vehVan_vehicle09",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SM_Steering_Wheel_vehVan_vehicle09",
    ],
    "vehTruck_vehicle04": [
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Wheel_Front_L_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Wheel_Front_R_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Wheel_Rear_L_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Wheel_Rear_R_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Door_Front_L_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Door_Front_R_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/Transparent/SM_All_Trans_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Frame_Interior_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Headlight_L_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Headlight_R_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Taillight_L_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Taillight_R_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Steering_Wheel_vehTruck_vehicle04",
    ],
    # Dual-rear-axle trucks: 6 wheels (front + rear + an extra "Axel3"
    # pair), not the standard 4 -- confirmed by direct folder inspection,
    # not assumed.
    "vehTruck_vehicle08": [
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Wheel_Front_L_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Wheel_Front_R_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Wheel_Rear_L_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Wheel_Rear_R_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Wheel_Axel3_L_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Wheel_Axel3_R_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Door_Front_L_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Door_Front_R_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/Transparent/SM_All_Trans_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Frame_Interior_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SM_Steering_Wheel_vehTruck_vehicle08",
    ],
    "vehTruck_vehicle11": [
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Wheel_Front_L_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Wheel_Front_R_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Wheel_Rear_L_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Wheel_Rear_R_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Wheel_Axel3_L_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Wheel_Axel3_R_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Door_Front_L_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Door_Front_R_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/Transparent/SM_All_Trans_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Frame_Interior_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Steering_Wheel_vehTruck_vehicle11",
    ],
    # Trailer: 3 axles (6 wheels), no doors -- no cab. Also no glass --
    # confirmed by direct folder inspection (its "Trans" mesh sits
    # directly under Mesh/, not a Transparent/ subfolder, and is a
    # tarp/cover mesh, not glass -- a cargo trailer has no windows).
    "vehTruck_trailer01": [
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SM_Wheel_Axel1_L_vehTruck_trailer01",
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SM_Wheel_Axel1_R_vehTruck_trailer01",
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SM_Wheel_Axel2_L_vehTruck_trailer01",
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SM_Wheel_Axel2_R_vehTruck_trailer01",
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SM_Wheel_Axel3_L_vehTruck_trailer01",
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SM_Wheel_Axel3_R_vehTruck_trailer01",
    ],
    # Bus: 4 wheels, no doors modeled this way (not simple hinged front
    # doors like the cars/trucks). Its glass mesh follows the trailer's
    # naming pattern ("SM_<name>_Trans", not "SM_All_Trans_<name>").
    "vehBus_vehicle10": [
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Wheel_Front_L_vehBus_vehicle10",
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Wheel_Front_R_vehBus_vehicle10",
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Wheel_Rear_L_vehBus_vehicle10",
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Wheel_Rear_R_vehBus_vehicle10",
        "/Game/Vehicle/vehBus_vehicle10/Mesh/Transparent/SM_vehBus_vehicle10_Trans",
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Frame_Interior_vehBus_vehicle10",
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Steering_Wheel_vehBus_vehicle10",
    ],
}


@dataclass(frozen=True)
class BuildingKit:  # pylint: disable=too-many-instance-attributes
    """One City Sample modular building kit (one floor style, e.g.
    ``Kit_Bldg_CHA_L1_A``): its real wall/corner/column/entrance asset
    paths plus the real horizontal grid and floor height its pieces tile
    on.

    Every dimension is a real, evidence-backed number, never guessed:
    ``wall_width_m``/``column_width_m``/``corner_to_first_wall_m`` are the
    BDF (``CHA_primary.bdf``) ``Mod_Dim`` widths of modules ``W1``/``P1``/
    ``C_E`` for this level, independently confirmed against the real
    per-instance spacing in ``All_Buildings_Lineup_pc`` (see
    ``building_placement.py``'s module-constants comment for the CHA_L1
    derivation); ``floor_height_m`` is the BDF ``Levels[N].Height``.

    Wall and entrance pieces share the same width/pivot convention (pivot
    at one width-edge, extending toward the other) so an entrance can
    substitute directly into any wall slot. ``column_asset_path`` (BDF
    module ``P1``) fills the gap between consecutive walls.

    ``wall_yaw_offset_rad``/``corner_yaw_offset_rad`` are this kit's
    mesh-local orientation conventions: the extra yaw added to a wall
    (and its column) / corner piece's per-edge tiling rotation so its
    decorative face points outward and its trim wraps the vertex flush.
    They are properties of the specific meshes, not universal: CHA_L1's
    (pi and pi/2) were live-screenshot-confirmed. Point-cloud yaw deltas
    suggest other kits share them, but that is inference -- confirm each
    new kit with a live orientation screenshot before trusting it.
    """

    wall_asset_path: str
    corner_asset_path: str
    corner_l_asset_path: str
    corner_r_asset_path: str
    entrance_asset_path: Optional[str]
    column_asset_path: str
    wall_width_m: float
    column_width_m: float
    corner_to_first_wall_m: float
    floor_height_m: float
    wall_yaw_offset_rad: float
    corner_yaw_offset_rad: float

    @property
    def wall_pitch_m(self) -> float:
        """Distance between consecutive wall pivots along an edge: one
        wall plus the column that fills the gap after it."""
        return self.wall_width_m + self.column_width_m


@dataclass(frozen=True)
class BuildingStyle:
    """An ordered stack of floor kits making up one building family (e.g.
    Epic's ``CHA``: L1 as the ground floor, then L2, L3, ...). Floor ``i``
    uses ``levels[i]``; floors past the end of ``levels`` repeat the last
    entry.

    All levels of one style must share the same horizontal grid (wall
    width, column width, corner reach) -- that is what lets a single
    quantized footprint tile correctly on every floor -- and a style
    rejects a mismatch at construction. Only floor heights may differ
    between levels (real CHA: L1 is 5.0m, L2..L11 are mostly 3.0m).
    """

    name: str
    levels: Tuple[BuildingKit, ...]

    def __post_init__(self) -> None:
        if not self.levels:
            raise ValueError("BuildingStyle needs at least one level")
        grid = self._grid(self.levels[0])
        for kit in self.levels[1:]:
            if self._grid(kit) != grid:
                raise ValueError(
                    f"BuildingStyle {self.name!r}: every level must share one horizontal "
                    f"grid (wall/column/corner widths), got {self._grid(kit)} != {grid}"
                )

    @staticmethod
    def _grid(kit: BuildingKit) -> Tuple[float, float, float]:
        return (kit.wall_width_m, kit.column_width_m, kit.corner_to_first_wall_m)

    @property
    def wall_pitch_m(self) -> float:
        """Shared wall-to-wall pitch of every level (see ``BuildingKit``)."""
        return self.levels[0].wall_pitch_m

    @property
    def wall_width_m(self) -> float:
        """Shared real wall width of every level."""
        return self.levels[0].wall_width_m

    @property
    def corner_to_first_wall_m(self) -> float:
        """Shared corner-vertex-to-first-wall distance of every level."""
        return self.levels[0].corner_to_first_wall_m

    def kit_for_floor(self, floor_index: int) -> BuildingKit:
        """The kit used by floor ``floor_index`` (0 = ground floor)."""
        return self.levels[min(floor_index, len(self.levels) - 1)]

    def floor_base_z(self, floor_index: int) -> float:
        """Height (meters) of floor ``floor_index``'s base above ground."""
        return sum(self.kit_for_floor(i).floor_height_m for i in range(floor_index))

    def total_height(self, floor_count: int) -> float:
        """Total height (meters) of a ``floor_count``-floor building."""
        return self.floor_base_z(floor_count)

    def floor_count_for_height(self, height: float) -> int:
        """Smallest floor count (at least 1) whose total height is at
        least ``height`` -- rounding up, never down."""
        floor_count = 1
        while self.total_height(floor_count) < height - _HEIGHT_EPSILON_METERS:
            floor_count += 1
        return floor_count


# Tolerance for comparing a sampled/stored height against a stack's exact
# cumulative floor heights (float sums of BDF heights like 5.0 + 3.0 * n).
_HEIGHT_EPSILON_METERS = 1e-6

# Migrated CHA floor styles: Kit_Bldg_CHA_L1_A .. L6_A. Real numbers, all
# from CHA_primary.bdf (Levels[N].Height and Modules[N].Mod_Dim), which
# also match the real point-cloud spacing measured for L1 (see
# building_placement.py's evidence comment):
#   - Height: L1 = 5.0m (ground floor), L2..L6 = 3.0m.
#   - Grid, identical for L1..L6: wall W1 3.25m, column P1 1.25m, corner
#     C_E 1.5m (BuildingStyle enforces that shared grid).
#   - L6 has BDF ``Repeat = 1`` and the real point cloud stacks it many
#     times (L6 x24 in building 5), so the last level repeating is real.
# Only CHA_L1's mesh-local yaw offsets (pi, pi/2) are live-screenshot
# confirmed; L2..L6 reuse them on point-cloud evidence (identical yaw
# deltas across kits) and must be confirmed live before being trusted.
_CHA_FLOOR_HEIGHTS_M = {1: 5.0, 2: 3.0, 3: 3.0, 4: 3.0, 5: 3.0, 6: 3.0}
# Levels that actually ship an Entrance mesh (the generator never emits it).
_CHA_LEVELS_WITH_ENTRANCE = {1, 2}


def _cha_kit(level: int) -> BuildingKit:
    """The real ``Kit_Bldg_CHA_L<level>_A`` kit (asset paths follow the
    real naming ``SM_BLDG_CHA_L0<level>_A_<Piece>_01_N1``)."""
    base = f"/Game/Building/CH/A/Kit_Bldg_CHA_L{level}_A/Mesh/SM_BLDG_CHA_L0{level}_A"
    return BuildingKit(
        wall_asset_path=f"{base}_Wall_01_N1",
        corner_asset_path=f"{base}_CornerEx_01_N1",
        corner_l_asset_path=f"{base}_CornerExL_01_N1",
        corner_r_asset_path=f"{base}_CornerExR_01_N1",
        entrance_asset_path=(
            f"{base}_Entrance_01_N1" if level in _CHA_LEVELS_WITH_ENTRANCE else None
        ),
        column_asset_path=f"{base}_Column_01_N1",
        wall_width_m=3.25,
        column_width_m=1.25,
        corner_to_first_wall_m=1.5,
        floor_height_m=_CHA_FLOOR_HEIGHTS_M[level],
        wall_yaw_offset_rad=math.pi,
        corner_yaw_offset_rad=math.pi / 2.0,
    )


BUILDING_KITS: Dict[str, BuildingKit] = {
    f"CHA_L{level}": _cha_kit(level) for level in _CHA_FLOOR_HEIGHTS_M
}

BUILDING_STYLES: Dict[str, BuildingStyle] = {
    "CHA": BuildingStyle(
        name="CHA", levels=tuple(BUILDING_KITS[f"CHA_L{level}"] for level in _CHA_FLOOR_HEIGHTS_M)
    ),
}

DEFAULT_BUILDING_STYLE: BuildingStyle = BUILDING_STYLES["CHA"]
