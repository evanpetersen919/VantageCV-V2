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

from typing import Dict, List

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
