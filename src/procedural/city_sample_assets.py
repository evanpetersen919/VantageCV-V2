"""Real City Sample asset paths for objects this project places
procedurally but no longer builds raw box geometry for -- vehicles as of
Phase 1 of the City Sample asset integration
(``feature/city-sample-asset-integration``); props and Hero landmark
buildings in later phases of that same effort.

Confirmed real (not guessed) via direct inspection of City Sample's
installed content at ``F:\\UE5Projects\\CitySample\\Content\\Vehicle\\``:
every non-hero vehicle folder has a ``BP_veh*_Sandbox.uasset`` Blueprint
-- the ``_Sandbox`` variant specifically, not the base/``_Destruction``/
``_Deformable`` variants, since a frozen-frame synthetic scenario has no
use for damage/deformation simulation and it likely sidesteps that
complexity. See KNOWN_GAPS_AND_ISSUES.md's Phase 0 investigation entry
for the full evidence (skeletal mesh + Animation Blueprint + Chaos
vehicle base classes confirm these are real Blueprint actors, not plain
static meshes).

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
every scenario template). Revisit once these assets are actually seen
in the editor during Phase 1's manual PIE verification pass.
"""

from typing import Dict, List

# Keys must match ActorPlacementGenerator's own VEHICLE_DIMENSIONS keys
# exactly (sedan/suv/truck/bus) -- see actor_placement.py and every
# scenario_templates/*.yaml's vehicle_mix block. City Sample has no
# distinct "van" category; the two van models are folded into "suv"
# (closer in size/role to a passenger SUV than to a cargo truck).
VEHICLE_ASSET_PATHS: Dict[str, List[str]] = {
    "sedan": [
        "/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
        "/Game/Vehicle/vehCar_vehicle03/BP_vehCar_vehicle03_Sandbox",
        "/Game/Vehicle/vehCar_vehicle05/BP_vehCar_vehicle05_Sandbox",
        "/Game/Vehicle/vehCar_vehicle06/BP_vehCar_vehicle06_Sandbox",
        "/Game/Vehicle/vehCar_vehicle07/BP_vehCar_vehicle07_Sandbox",
    ],
    "suv": [
        "/Game/Vehicle/vehCar_vehicle12/BP_vehCar_vehicle12_Sandbox",
        "/Game/Vehicle/vehCar_vehicle13/BP_vehCar_vehicle13_Sandbox",
        "/Game/Vehicle/vehVan_vehicle01/BP_vehVan_vehicle01_Sandbox",
        "/Game/Vehicle/vehVan_vehicle09/BP_vehVan_vehicle09_Sandbox",
    ],
    "truck": [
        "/Game/Vehicle/vehTruck_vehicle04/BP_vehTruck_vehicle04_Sandbox",
        "/Game/Vehicle/vehTruck_vehicle08/BP_vehTruck_vehicle08_Sandbox",
        "/Game/Vehicle/vehTruck_vehicle11/BP_vehTruck_vehicle11_Sandbox",
        "/Game/Vehicle/vehTruck_trailer01/BP_vehTruck_trailer01_Sandbox",
    ],
    "bus": [
        "/Game/Vehicle/vehBus_vehicle10/BP_vehBus_vehicle10_Sandbox",
    ],
}
