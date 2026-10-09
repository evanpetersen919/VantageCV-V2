### [OPEN, NOT RESOLVED -- paused after a real regression] Traffic-light pole color can't be safely driven yet

User asked whether the real traffic-signal pole mesh's color (currently
always whatever its baked material defaults to -- see `traffic_lights.py`'s
own "Not done, on purpose" note) could be switched to match
`signal_phasing.py`'s resolved phase, alongside the green-axis
flow-through work (see the two "vehicles flow through" entries above).

**What was found, real and confirmed live** (headless
`UnrealEditor.exe -ExecutePythonScript` queries, not guessed):
the mesh `SM_StreetLamp_A_StopLight_D` (used by `traffic_lights.py`)
has its emissive signal face on material slot 1
(`/Game/Prop/Kit_StreetLamp_A/Material/M_Prop_Emissive_Traffic_
StopLight`), a `MaterialInstanceConstant` whose parent chain is
`MI_StopLight_Crosswalk` -> `M_StopLight_Main`. It exposes real scalar
parameters `"Red Light Intensity"`/`"Yellow Light Intensity"`/`"Green
Light Intensity"` (each baked to 80.0 by default, all three
simultaneously) and a real static switch **`"MassTraffic Controlled"`**,
confirmed live to be `True` on this asset (inherited, not itself
overridden here). This switch gates the compiled shader permutation:
when true, color selection is very likely routed through Epic's Mass-AI
per-instance packed-data channel (`"MassTraffic PackedParam1"`, a
scalar also present on this material, confirmed at `0.0`/unset in this
project since it never uses Mass AI/ISM instancing at all -- see the
"vehicles flow through" entries' own citation of why
`ACitySampleVehicleBase`/Mass traffic was never ported here), which
would make the plain named intensity scalars structurally inert
regardless of what a runtime `MaterialInstanceDynamic` sets them to --
the same class of bug as the `Animate` static-switch issue earlier in
this file, just on a different asset.

**The real mistake made while chasing this**: rather than duplicating
`M_Prop_Emissive_Traffic_StopLight` into a new, project-owned instance
first, a headless script flipped `"MassTraffic Controlled"` to `False`
**directly on the shared, original Epic asset** and saved it. A
same-process readback and even a genuinely fresh separate-process
readback both showed the change had persisted, and a live screenshot
appeared (at a glance) to show the pole's color correctly matching the
resolved phase. **This was wrong**: the user, watching the actual live
game, reported the light was now off everywhere, with no green
anywhere -- i.e. the edit broke something else (this material is very
likely shared by other meshes/usages across the project, so a global
edit that "worked" for one specific pole broke rendering elsewhere).
This was caught, and `"MassTraffic Controlled"` was reverted back to
`True` the same way it was changed (`set_material_instance_static_
switch_parameter_value` + `update_material_instance` + save + wait),
confirmed restored via a fresh separate process
(`MassTraffic Controlled = True`). All Python-side plumbing added for
this feature (`FacadePiece.material_scalar_overrides`, `signal_phasing.
resolve_signal_color`, `traffic_lights.py`'s color-override logic,
`dataset_generator.py`'s `active_phases` threading) was reverted too,
uncommitted, rather than leaving a mechanism in place that visibly does
nothing under the asset's real (restored) default state -- shipping
that would be exactly the kind of half-finished feature this project
avoids.

**Real lesson for a future attempt**: never flip a static switch (or
any override) directly on a shared, originally-Epic-authored asset
that other content might also reference. Duplicate it first into a
project-owned copy (e.g.
`/Game/Prop/Kit_StreetLamp_A/Material/MI_VantageCV_TrafficStopLight`,
created via `unreal.AssetToolsHelpers.get_asset_tools().duplicate_
asset(...)` or equivalent), verify NOTHING else in the project
references the original with the assumption `"MassTraffic Controlled"
== True` (e.g. via `unreal.AssetRegistryHelpers`'s referencer query),
point ONLY `traffic_lights.py`'s own mesh/material assignment at the
new copy, and only then flip the switch there -- so the blast radius of
any mistake is provably limited to this project's own new asset, never
Epic's shared original. Also: a live screenshot "looking right" is not
sufficient confirmation for a change with unknown blast radius across a
large city scene -- the user's own live observation caught what the
screenshot-based check missed twice in a row this session, and should
have been asked for before declaring success, not after.

Vehicle/pedestrian green-axis flow-through logic (the primary ask) is
unaffected by any of this -- it's pure Python placement logic, fully
covered by deterministic unit tests, and was never part of the mistake.
