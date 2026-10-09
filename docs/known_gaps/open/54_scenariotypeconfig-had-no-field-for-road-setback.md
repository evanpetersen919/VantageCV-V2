### [RESOLVED] `ScenarioTypeConfig` had no field for road setback
Was: `building_placement.py`'s `ROAD_SETBACK_METERS = 2.0` was a fixed
module constant, not read from config, because no such field existed on
`ScenarioTypeConfig` and MASTER_PROMPT never specifies one.

Resolved by `ScenarioTypeConfig.road_setback_meters` (pydantic field,
`>= 0` validated, default `2.0` matching the old constant exactly so
every pre-existing caller/template kept working unchanged).
`BuildingPlacementGenerator._too_close_to_road` was converted from a
`@staticmethod` to an instance method to read `self.config
.road_setback_meters` instead of the module constant, which was removed
entirely (no more second source of truth to drift out of sync).
`config_loader.py` maps it from a template's optional
`buildings.road_setback_meters` YAML key (omitted entirely, not defaulted
to a duplicate literal, when absent -- so a template that doesn't set it
gets `ScenarioTypeConfig`'s own default from the one place it's actually
defined). `urban_dense.yaml` and `urban_sparse.yaml` now set genuinely
different values (`2.0` vs `4.0`) -- a real per-scenario-type value, not
just a config field that exists but is never actually varied. A
dedicated test (`test_custom_road_setback_meters_is_actually_respected`)
confirms the field is genuinely wired through to generated placement,
not merely validated and silently ignored.

