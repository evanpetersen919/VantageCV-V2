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
which would have required two different code paths). Real, known
limitation: this is the body shell only, without wheels/doors/interior
detail (those are separate ``SM_Wheel_*``/``SM_Door_*`` meshes) -- a
visibly correct, recognizable vehicle silhouette, not full visual
fidelity; a real future improvement, not attempted here.

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
