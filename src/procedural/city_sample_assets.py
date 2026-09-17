"""Real City Sample asset paths for objects this project places
procedurally but no longer builds raw box geometry for -- vehicles as of
Phase 1 of the City Sample asset integration
(``feature/city-sample-asset-integration``); props and Hero landmark
buildings in later phases of that same effort.

These are combined skeletal mesh assets (``SKM_<vehicle folder>``), not
the ``BP_veh*_Sandbox`` driveable-vehicle Blueprints City Sample itself
uses. Real, live PIE verification (2026-09-16, see
KNOWN_GAPS_AND_ISSUES.md) found that every ``_Sandbox`` Blueprint's
parent chain ultimately depends on ``ACitySampleVehicleBase`` -- a
native C++ class defined in CitySample's own game-project *source*
(``Source/CitySample/Vehicles/CitySampleVehicleBase.h``), not portable
content. That class is itself deeply wired into CitySample's own
gameplay framework (Mass AI traffic control, Enhanced Input, a custom
UI/menu system, photo mode, ``ACitySampleCharacter``) -- none of which
this project needs (scenarios are frozen-frame captures, not
driveable), and porting it would mean dragging in a large, open-ended
slice of CitySample's game framework for no benefit. The skeletal mesh
itself, by contrast, is genuine portable content with no such
dependency -- confirmed via direct inspection of every migrated
vehicle's ``Content/Vehicle/<folder>/Mesh/`` subfolder.

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
        "/Game/Vehicle/vehCar_vehicle02/Mesh/SKM_vehCar_vehicle02",
        "/Game/Vehicle/vehCar_vehicle03/Mesh/SKM_vehCar_vehicle03",
        "/Game/Vehicle/vehCar_vehicle05/Mesh/SKM_vehCar_vehicle05",
        "/Game/Vehicle/vehCar_vehicle06/Mesh/SKM_vehCar_vehicle06",
        "/Game/Vehicle/vehCar_vehicle07/Mesh/SKM_vehCar_vehicle07",
    ],
    "suv": [
        "/Game/Vehicle/vehCar_vehicle12/Mesh/SKM_vehCar_vehicle12",
        "/Game/Vehicle/vehCar_vehicle13/Mesh/SKM_vehCar_vehicle13",
        "/Game/Vehicle/vehVan_vehicle01/Mesh/SKM_vehVan_vehicle01",
        "/Game/Vehicle/vehVan_vehicle09/Mesh/SKM_vehVan_vehicle09",
    ],
    "truck": [
        "/Game/Vehicle/vehTruck_vehicle04/Mesh/SKM_vehTruck_vehicle04",
        "/Game/Vehicle/vehTruck_vehicle08/Mesh/SKM_vehTruck_vehicle08",
        "/Game/Vehicle/vehTruck_vehicle11/Mesh/SKM_vehTruck_vehicle11",
        "/Game/Vehicle/vehTruck_trailer01/Mesh/SKM_vehTruck_trailer01",
    ],
    "bus": [
        "/Game/Vehicle/vehBus_vehicle10/Mesh/SKM_vehBus_vehicle10",
    ],
}
