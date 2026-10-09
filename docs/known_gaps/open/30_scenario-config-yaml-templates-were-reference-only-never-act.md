### [RESOLVED] Scenario config YAML templates were reference-only, never actually loaded
Was: no code anywhere loaded `configs/scenario_templates/*.yaml` at
runtime; every `ScenarioTypeConfig` used in tests/examples/the user guide
was constructed directly in Python.

Resolved by `src/utils/config_loader.py`'s `load_scenario_config`: maps a
template's nested YAML (`road_network:`/`buildings:`/`traffic:` sections)
onto `ScenarioTypeConfig`'s flat constructor fields. Only two of the five
templates are actually loadable this way, though: `urban_dense.yaml` and
`urban_sparse.yaml` share `ScenarioTypeConfig`'s schema because
`RoadNetworkGenerator` implements exactly one generation strategy
(perturbed-grid + Delaunay) regardless of `scenario_type` -- it never
branches on it. `highway.yaml`, `parking_lot.yaml`, and `roundabout.yaml`
describe entirely different, never-implemented generation strategies (see
the Highway `BLOCKER-for-later` entry and the "No parking spawn zones"
entry below) and don't even share `ScenarioTypeConfig`'s field names.
Loading one of those three raises `NotImplementedError` with a message
explaining why, rather than a confusing `KeyError`/`pydantic.ValidationError`
or a silently-wrong config. This is a deliberate, honest scope boundary,
not a partial implementation to revisit -- the fix for those three
templates is implementing their own road-generation strategies (separate,
larger pieces of work each), not extending this loader.

