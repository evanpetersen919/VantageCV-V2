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

# Real City Sample pedestrian meshes -- Vertex Animation Texture (VAT)
# static meshes from Content/Crowd/VAT/Meshes, not the ``BP_CrowdCharacter``
# Blueprint City Sample itself uses for its Mass-AI-driven crowd. Both
# alternatives were investigated first, mirroring the vehicle
# investigation above (see KNOWN_GAPS_AND_ISSUES.md for the full
# research): ``BP_CrowdCharacter``'s native parent
# (``ACitySampleCrowdCharacter``, ``Source/CitySample/Crowd/
# CrowdCharacterActor.h``) is not portable content, same as
# ``ACitySampleVehicleBase`` for vehicles. Unlike vehicles, though, this
# project's own source investigation found City Sample's crowd
# AnimInstance chain has no hard Mass AI dependency for a stationary
# actor's pose -- but that path still needs new skeletal-mesh spawn code
# this project doesn't have yet, so VAT (already a plain static mesh, no
# skeleton, no AnimBlueprint, same "no pose dependency" property that
# made ``SM_Frame_<vehicle>`` work) is the lower-risk starting choice.
#
# Confirmed live (2026-09-22): ``SM_f_tal_nrw_combined`` (female,
# normal-weight, one pre-assembled outfit -- no separate body/clothing
# part assembly needed, unlike vehicles) renders a real, natural
# mid-stride walking pose unconditionally, with no skeleton, AnimBP, or
# Mass AI runtime involved at all -- confirmed via a real screenshot,
# not just a clean spawn log (this project's own established standard
# of evidence). Only one variant migrated/verified so far; more
# gender/weight/outfit variants are a real, deliberate fast-follow for
# visual diversity, not done yet.
PEDESTRIAN_ASSET_PATHS: List[str] = [
    "/Game/Crowd/VAT/Meshes/SM_f_tal_nrw_combined",
]


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
    column_asset_path: Optional[str]
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
    Epic's ``CHA``: L1 as the ground floor, then L2, L3, ...).

    ``levels`` are the floors from the ground up; the LAST one is the
    repeating floor (BDF ``Repeat=1``), which fills any extra height.
    ``top_levels`` are the crown floors that finish a tall building. A
    ``floor_count``-floor building uses:
    - fewer floors than ``len(levels) + len(top_levels)`` (or no crown):
      ``levels`` from the ground up, then repeats of the last level --
      no crown;
    - otherwise: ``levels``, extra repeats of the last level, then all
      of ``top_levels`` on top.
    Evidence (real point cloud, CHA buildings 5 and 9): L1-L5, then L6
    repeated many times, then L7-L10 on top; the short building 8 is
    just L1-L5 with no crown. The exact minimum height for a crown is an
    inference from those buildings, not measured.

    All levels (and crown levels) of one style must share the same
    horizontal grid (wall width, column width, corner reach) -- that is
    what lets a single quantized footprint tile correctly on every floor
    -- and a style rejects a mismatch at construction. Only floor heights
    may differ between levels (real CHA: L1 is 5.0m, L2..L11 mostly 3.0m).
    """

    name: str
    levels: Tuple[BuildingKit, ...]
    top_levels: Tuple[BuildingKit, ...] = ()
    # Optional cap layer tiled once on top of the last floor (Epic's
    # "Topper": a short parapet kit over the roof edge; it uses the same
    # wall/corner grammar and grid as the floors below). Counts toward the
    # building's total height but is not a floor.
    roof_cap: Optional[BuildingKit] = None
    # Distance (m) the flat roof slab is inset from the walls (BDF
    # ``Roof_Inset``).
    roof_inset_m: float = 0.2

    def __post_init__(self) -> None:
        if not self.levels:
            raise ValueError("BuildingStyle needs at least one level")
        grid = self._grid(self.levels[0])
        extra = (self.roof_cap,) if self.roof_cap is not None else ()
        for kit in self.levels[1:] + self.top_levels + extra:
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
    def column_width_m(self) -> float:
        """Shared real column (gap-filler) width of every level."""
        return self.levels[0].column_width_m

    def edge_length_for_wall_count(self, wall_count: int) -> float:
        """Exact edge length holding ``wall_count`` walls: a corner reach
        at BOTH ends plus the walls and the ``wall_count - 1`` columns
        between them (``2C + N*W + (N-1)*P``). Measured on 48/48 real CHA
        and CHH edges: the last wall ends exactly one corner reach short
        of the far vertex."""
        return (
            2.0 * self.corner_to_first_wall_m
            + wall_count * self.wall_width_m
            + (wall_count - 1) * self.column_width_m
        )

    def wall_count_for_edge_length(self, edge_length: float) -> int:
        """Inverse of ``edge_length_for_wall_count`` for an exact fit."""
        return round(
            (edge_length - 2.0 * self.corner_to_first_wall_m + self.column_width_m)
            / self.wall_pitch_m
        )

    @property
    def corner_to_first_wall_m(self) -> float:
        """Shared corner-vertex-to-first-wall distance of every level."""
        return self.levels[0].corner_to_first_wall_m

    def floor_kits(self, floor_count: int) -> List[BuildingKit]:
        """The kit of every floor (ground floor first) of a
        ``floor_count``-floor building -- see the class docstring."""
        bottom = len(self.levels)
        if self.top_levels and floor_count >= bottom + len(self.top_levels):
            repeats = floor_count - bottom - len(self.top_levels)
            return list(self.levels) + [self.levels[-1]] * repeats + list(self.top_levels)
        if floor_count <= bottom:
            return list(self.levels[:floor_count])
        return list(self.levels) + [self.levels[-1]] * (floor_count - bottom)

    def layer_kits(self, floor_count: int) -> List[BuildingKit]:
        """Every tiled layer of a ``floor_count``-floor building, ground
        first: the floors, then the roof cap when the style has one."""
        layers = self.floor_kits(floor_count)
        if self.roof_cap is not None:
            layers.append(self.roof_cap)
        return layers

    def roof_plane_height(self, floor_count: int) -> float:
        """Height (meters) of the top of the last FLOOR -- where the flat
        roof slab sits (Epic's roof plane is at the top of the last floor,
        within 5cm; a roof cap's parapet rises around it)."""
        return sum(kit.floor_height_m for kit in self.floor_kits(floor_count))

    def total_height(self, floor_count: int) -> float:
        """Total height (meters) of a ``floor_count``-floor building,
        including the roof cap when the style has one."""
        return sum(kit.floor_height_m for kit in self.layer_kits(floor_count))

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
# Crown floors L7..L10 (BDF Heights 2.75, 3.0, 3.0, 3.0): real towers stack
# L1-L5, L6 repeated, then L7-L10 on top (point cloud buildings 5 and 9).
_CHA_TOP_FLOOR_HEIGHTS_M = {7: 2.75, 8: 3.0, 9: 3.0, 10: 3.0}
# Levels that actually ship an Entrance mesh (the generator never emits it).
_CHA_LEVELS_WITH_ENTRANCE = {1, 2}

# Migrated CHH floor styles: Kit_Bldg_CHH_L1_A .. L4_A, from CHH_primary.bdf
# and the real point cloud (4 real buildings, read-only survey):
#   - Height: L1 3.25m, L2 2.25m, L3 3.75m, L4 4.25m; L4 has BDF Repeat=1
#     and real towers repeat it (z-steps 3.25, 2.25, 3.75, then 4.25 x N).
#   - Grid, identical for L1..L4: corner C_E 1.0m; facade grammar
#     ``C1|W1|(W2-W1)*|W2|(W1-W2)*|W1|C1`` -- the small W1 (1.25m) sits at
#     both ends of every edge with the large W2 (3.25m) alternating
#     between. In our wall/column model that is "wall" = Wall_01 (W1) and
#     "column" = Wall_02 (W2), giving Corner, W, P, W, ..., W, Corner.
#   - Measured: corner-to-first-wall exactly 100cm on every level; Wall_02
#     has the same yaw as Wall_01 on the same edge; corner and wall yaw
#     deltas match CHA (270/270 vs the edge direction), so the CHA offsets
#     are reused -- live-screenshot confirmed.
#   - No Entrance mesh ships in these kits.
_CHH_FLOOR_HEIGHTS_M = {1: 3.25, 2: 2.25, 3: 3.75, 4: 4.25}

# Migrated SFA floor styles: Kit_Bldg_SFA_L1_A .. L5_A, from SFA_primary.bdf
# and the point cloud (read-only survey):
#   - Height: L1 12.75m, L2 7.5m, L3 11.25m, L4 3.75m, L5 3.75m (L5 has BDF
#     Repeat=1); L6-L9 are toppers and are not migrated.
#   - Grid: corner C_E 1.5m, wall W1 3.25m, NO columns (grammar
#     ``C1|(W1)*|...|C1``); measured Wall_01 pitch exactly 325cm (0 of 5798
#     walls scaled) and corner reach 150cm.
#   - Mesh names are ``SM_BLDG_SFA_L<n>_A_...`` (level NOT zero-padded).
#   - Yaw deltas match CHA (270/270); offsets reused, confirm live.
_SFA_FLOOR_HEIGHTS_M = {1: 12.75, 2: 7.5, 3: 11.25, 4: 3.75, 5: 3.75}

# Roof caps ("Toppers"), from the BDF ``Topper`` fields and a read-only
# point-cloud survey: a Topper number is just another level's kit, tiled on
# the same footprint edges (same yaw as the walls) at the top of the last
# floor. CHH floors L4-L6 use Topper 8 (Kit_Bldg_CHH_L8_A, BDF Height 1.0m,
# same C 1.0 / W1 1.25 / W2 3.25 grid); SFA floors L3-L8 use Topper 9
# (Kit_Bldg_SFA_L9_A, Height 1.0m, same C 1.5 / W 3.25 grid). Both share the
# floors' grid exactly. NOT done: CHA's cap (L19 / L20) -- L19 uses a
# different grid (corner 1.0m, walls 3.25m and 1.75m), which this tiling
# model cannot express yet. The cap's mesh-local yaw offsets are assumed to
# match the floors' (same yaw deltas in the point cloud); confirm live.
_CHH_CAP_LEVEL = 8
_SFA_CAP_LEVEL = 9
_CAP_HEIGHT_M = 1.0

# Roof slab inset from the walls, BDF ``Roof_Inset`` per family.
_ROOF_INSET_M = {"CHA": 0.2, "CHH": 0.6, "SFA": 1.0}


def _family_kit(  # pylint: disable=too-many-arguments
    region: str,
    family: str,
    letter: str,
    level: int,
    *,
    wall_piece: str,
    column_piece: Optional[str],
    wall_width_m: float,
    column_width_m: float,
    corner_to_first_wall_m: float,
    floor_height_m: float,
    pad_level: bool = True,
    has_entrance: bool = False,
) -> BuildingKit:
    """The real ``Kit_Bldg_<family>_L<level>_A`` kit under
    ``/Game/Building/<region>/<letter>/``. Mesh names follow Epic's
    ``SM_BLDG_<family>_L<tag>_A_<Piece>_N1``, where the level tag is
    zero-padded to two digits for CH families (``L01``) but not for SFA
    (``L1``) -- ``pad_level`` selects which."""
    tag = f"{level:02d}" if pad_level else str(level)
    base = (
        f"/Game/Building/{region}/{letter}/Kit_Bldg_{family}_L{level}_A/Mesh/"
        f"SM_BLDG_{family}_L{tag}_A"
    )
    return BuildingKit(
        wall_asset_path=f"{base}_{wall_piece}_N1",
        corner_asset_path=f"{base}_CornerEx_01_N1",
        corner_l_asset_path=f"{base}_CornerExL_01_N1",
        corner_r_asset_path=f"{base}_CornerExR_01_N1",
        entrance_asset_path=f"{base}_Entrance_01_N1" if has_entrance else None,
        column_asset_path=f"{base}_{column_piece}_N1" if column_piece else None,
        wall_width_m=wall_width_m,
        column_width_m=column_width_m,
        corner_to_first_wall_m=corner_to_first_wall_m,
        floor_height_m=floor_height_m,
        wall_yaw_offset_rad=math.pi,
        corner_yaw_offset_rad=math.pi / 2.0,
    )


BUILDING_KITS: Dict[str, BuildingKit] = {}
for _level, _height in {**_CHA_FLOOR_HEIGHTS_M, **_CHA_TOP_FLOOR_HEIGHTS_M}.items():
    BUILDING_KITS[f"CHA_L{_level}"] = _family_kit(
        "CH",
        "CHA",
        "A",
        _level,
        wall_piece="Wall_01",
        column_piece="Column_01",
        wall_width_m=3.25,
        column_width_m=1.25,
        corner_to_first_wall_m=1.5,
        floor_height_m=_height,
        has_entrance=_level in _CHA_LEVELS_WITH_ENTRANCE,
    )
for _level, _height in _CHH_FLOOR_HEIGHTS_M.items():
    BUILDING_KITS[f"CHH_L{_level}"] = _family_kit(
        "CH",
        "CHH",
        "H",
        _level,
        wall_piece="Wall_01",
        column_piece="Wall_02",
        wall_width_m=1.25,
        column_width_m=3.25,
        corner_to_first_wall_m=1.0,
        floor_height_m=_height,
    )
for _level, _height in _SFA_FLOOR_HEIGHTS_M.items():
    BUILDING_KITS[f"SFA_L{_level}"] = _family_kit(
        "SF",
        "SFA",
        "A",
        _level,
        wall_piece="Wall_01",
        column_piece=None,
        wall_width_m=3.25,
        column_width_m=0.0,
        corner_to_first_wall_m=1.5,
        floor_height_m=_height,
        pad_level=False,
    )


BUILDING_KITS["CHH_L8"] = _family_kit(
    "CH",
    "CHH",
    "H",
    _CHH_CAP_LEVEL,
    wall_piece="Wall_01",
    column_piece="Wall_02",
    wall_width_m=1.25,
    column_width_m=3.25,
    corner_to_first_wall_m=1.0,
    floor_height_m=_CAP_HEIGHT_M,
)
BUILDING_KITS["SFA_L9"] = _family_kit(
    "SF",
    "SFA",
    "A",
    _SFA_CAP_LEVEL,
    wall_piece="Wall_01",
    column_piece=None,
    wall_width_m=3.25,
    column_width_m=0.0,
    corner_to_first_wall_m=1.5,
    floor_height_m=_CAP_HEIGHT_M,
    pad_level=False,
)


def _kits(family: str, levels: Dict[int, float]) -> Tuple[BuildingKit, ...]:
    return tuple(BUILDING_KITS[f"{family}_L{level}"] for level in levels)


BUILDING_STYLES: Dict[str, BuildingStyle] = {
    "CHA": BuildingStyle(
        name="CHA",
        levels=_kits("CHA", _CHA_FLOOR_HEIGHTS_M),
        top_levels=_kits("CHA", _CHA_TOP_FLOOR_HEIGHTS_M),
        roof_inset_m=_ROOF_INSET_M["CHA"],
    ),
    "CHH": BuildingStyle(
        name="CHH",
        levels=_kits("CHH", _CHH_FLOOR_HEIGHTS_M),
        roof_cap=BUILDING_KITS["CHH_L8"],
        roof_inset_m=_ROOF_INSET_M["CHH"],
    ),
    "SFA": BuildingStyle(
        name="SFA",
        levels=_kits("SFA", _SFA_FLOOR_HEIGHTS_M),
        roof_cap=BUILDING_KITS["SFA_L9"],
        roof_inset_m=_ROOF_INSET_M["SFA"],
    ),
}

DEFAULT_BUILDING_STYLE: BuildingStyle = BUILDING_STYLES["CHA"]
