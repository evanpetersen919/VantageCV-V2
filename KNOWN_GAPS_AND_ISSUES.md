# Known Gaps, Risks & Open Issues

Living log of everything deferred, unverified, or risky in this implementation,
so nothing gets silently lost between sessions/phases. Update this file whenever
a gap is discovered, deferred, or closed. Never delete a closed entry — mark it
`RESOLVED` with the phase/commit that fixed it.

Severity: **BLOCKER** (must fix before shipping) / **RISK** (works but fragile,
should fix before relying on it) / **DEFERRED** (intentionally postponed to a
later phase, tracked so it isn't forgotten).

---

## Open

### [RESOLVED, bare trees only] No trees -- now street birches in tree bases along the sidewalks
`street_furniture.py` (extended) places a tree base and a birch at the same spot about every 20m along each sidewalk. MEASURED from Epic's 188 real birch placements: consecutive pits about 20m apart (median 2021cm), 1:1 pairing with a base at identical position, base scale 1.2, tree scale uniform 0.8-1.1, random yaw, commonest variants f/g/h (154 of 188), base at sidewalk-top height. INFERRED (Epic puts trees in plazas and courtyards, not along curbs): the pit sits 1.5m from the curb line, the middle of our 3m sidewalk. A tree whose spot lands on a lamp is nudged up to 3.5m along the curb instead of dropped. Position is deterministic; each tree's scale, yaw and variant are random per scenario seed (`seed` argument), the base style (round/square, grill/no grill) is one per scenario. Verified live in a real generated city: trees sit in their bases on the sidewalk between lamps and meters, at street scale.

**Real limitation found**: Epic's birches are BARE. `Kit_Tree_Birch` ships only a bark material (`M_tree_birch` and three bark textures, no leaf material), so the crown is branches only -- a winter look under our summer sky. `Kit_Tree_Maple_Red` (38MB) and `Kit_Tree_Maple_Sugar` (85MB) ship a separate leaf "Cap" material with an opacity texture and would be leafy; they are not migrated. Nanite: the meshes render fine under `-d3d11` (a reduced fallback), no crash seen.

### [RESOLVED, first pass] Sidewalks were empty -- now real street furniture along every curb
**Evidence**: Epic's real `CITY_street_furniture_sidewalk` point cloud (about 15,000 placements), measured relative to the curb line. Every item is unscaled and has its pivot at road-crown height (the base sinks into the raised sidewalk, so z = 0). `src/procedural/street_furniture.py` places, outward from our curb line (the outer pavement edge, now the shared `road_edge_kit.edge_runs`): parking meters every 7.00m at 25cm, street lamps about every 14.35m at 40cm, hydrants about every 27.9m at 30cm, trash cans about every 12.35m at 40cm and no-parking signs about every 33.4m at 55cm. Items keep 5m clear of each run's ends (the intersection zone) and 1.0-1.2m clear of higher-priority items (lamps first, then hydrants, signs, trash cans, meters). One lamp style (cobra-head `Kit_StreetLamp_A` pole, or ornate `Kit_StreetLamp_C`/`E`) per scenario, chosen from the seed like the curb/sidewalk style; placement is deterministic. `ScenarioResult.street_furniture_pieces` are `static_asset` entries after the facade and curb/sidewalk pieces.

**Orientation was verified live, not assumed**: each item was placed on a real sidewalk at four rotations and screenshotted from the side and straight down (with asymmetric spacing to tell which rotation is which). Every item looks right at the run's own rotation except the cobra-head lamp, whose arm points over the road at run rotation + pi. Mailboxes and fire call boxes were left out because their fronts could not be told apart from above. Verified in a real generated 56-building city (street level, both a bus and buildings in frame).

**Migrated**: `Parking_Meter_00`, `Fire_Hydrant_02` (`_00`, `Mailbox_00`, `Fire_Call_Box_00` also migrated, unused), `No_Parking_Road_Sign_00`, `Kit_Trashcan_A`, `Kit_StreetLamp_C`/`E` (verified file-for-file). Not done: bus stops, news dispensers, bollards, traffic lights, lamp banners, benches; trees (next); the real spacing varies per item so a real city's rhythm is approximated with fixed spacings and phases; real meters exist only on parking curbs (ours are on every curb).

### [RESOLVED, mostly] Buildings were open-topped -- now flat roof slabs plus real roof caps on CHH and SFA
**Evidence (read-only survey of CitySample's Houdini `Building.hda` and the real building point cloud)**: City Sample has no roof mesh. A BDF `Topper` number is just another level's kit, tiled on the same footprint edges (same yaw as the walls) at the top of the last floor; the flat roof itself is a thin plane extruded at the top of the last floor (measured within 5cm of it) with a bitumen/pebble-tar material (`MI_Rooftop_*`, picked per building), inset from the walls by the BDF `Roof_Inset` (CHA 0.2m, CHH 0.6m, SFA 1.0m).

**What was built**: `src/procedural/roofs.py` adds one upward-facing roof quad per building at the top of its last floor (+5cm), inset by the family's `Roof_Inset` (`BuildingStyle.roof_inset_m`), with a new `"roof"` material tag (added in `serialize_scenario` alongside the ground and block paving). `BuildingStyle` gained an optional `roof_cap`, a kit tiled once above the last floor on the same footprint: CHH uses `Kit_Bldg_CHH_L8_A`, SFA uses `Kit_Bldg_SFA_L9_A` (both 1.0m per the BDF and on exactly the floors' wall grid, enforced at construction). The cap counts toward total height but is not a floor (`layer_kits`, `roof_plane_height`, `total_height`). Verified live: a parapet of top-piece walls ringing a flat tar-coloured slab on a CHH tower, and every building in a real generated 56-building city closed from above.

**Migrated for this**: `CHH_L5/L7/L8`, `SFA_L9`, `CHA_L19` (all verified file-for-file).

**Not done**: CHA has no cap: its cap kit `L19` uses a different grid (corner 1.0m, walls 3.25m and 1.75m, versus the floors' 1.5/3.25/1.25), which the tiling model cannot express yet; real CHA towers also end in `L20`, a 9.3m rotunda kit that is not migrated. The roof uses the migrated matte asphalt (Epic's own `MI_Rooftop_*` roof materials are 71MB+ of 8K textures and not migrated); rooftop props (AC units, vents, antennas: Blueprints from a 1.2GB folder) are not placed; CHH's real tall-tower crown (`L7`, 5.75m) is not used; the cap's mesh-local yaw offsets are assumed equal to the floors' (they looked correct in the CHH screenshot, but were not checked against SFA closely).

### [RESOLVED, first stage] Roads were flat mirror-like strips with no curbs or sidewalks -- now real curbs and sidewalks, and matte asphalt
**What was built** (`src/procedural/road_edge_kit.py`, `generate_scenario` -> `ScenarioResult.road_edge_pieces`, serialized as `static_asset` entries): along the outer pavement edge of every directed road edge (the outermost lane's outer boundary, already trimmed at intersections) it places Megascans `Modular_Curb_5_M_*` (5m, placed at scale `(sx, -0.75, 0.75)` exactly as Epic places every curb, from 14,551 real placements) and `SM_Sidewalk_6_3_A..E` (6m x 3m, 3m outward; real `sidewalk_width` is 3m in Epic's Houdini config), each run stretched by `round(length/tile)` pieces so it fills exactly (Epic stretches its last piece the same way). Every number was measured in the engine (`GetStaticMeshBounds`) and the placement was first hand-built and screenshot-verified on a straight 30m road before being coded; heights put the sidewalk top ~10.8cm and curb top ~11cm above the road. Building setback is now at least the 3m sidewalk width (`SIDEWALK_WIDTH_METERS` in `lane_topology.py`) so no building stands on a sidewalk. Verified live on a real generated 56-building city (aerial and street level).

**Road gloss root cause and fix**: the plain `M_Asphalt_Master_Inst` rendered every generated road as a perfect mirror (base roughness 0.22 plus a puddle layer that is fully on for our meshes). Raising `BaseRoughnessMult`, zeroing the puddle parameters and giving the meshes black vertex colours all changed nothing (all reverted). What worked: point the `"asphalt"` tag at Epic's own matte parking-lot variant, `M_Asphalt_Master_Inst_ParkingLots` (already migrated). Sidewalk-side effect: roads and the ground plane now share a material.

**Migrated for this (all verified file-for-file)**: `Road/Kit_City_Road` (real road tiles, not used yet), `Road/Kit_MeshDecals_A` (lane paint, not used yet), the three `M_Asphalt_Master_Inst_{Intersection,Crosswalk,BufferIntersection}` materials, `Modular_Curb_5_M_00/01/02`, `Modular_Sidewalk_Corner_4m_00`. Measured bounds of the real road tiles (pivot at the start, centered, 20.04m wide for the 19m class, crowned top ~56cm) are recorded in the project memory for the next stage.

**Follow-up fixes (user-reported)**: (1) the sidewalk raised the floor but dropped back to road height before the buildings -- `block_pavement.py` now fills every city block (inset by the road half-width, i.e. the curb line) with one sidewalk-height quad using Epic's sidewalk material, so the surface runs flush from the curb to the building fronts and also covers the intersection-corner gaps; block identification was refactored into the public `identify_city_blocks` for this. (2) Curb and sidewalk tiles were varying per tile (a real city uses one sidewalk type): each scenario now uses ONE curb style and ONE sidewalk style, chosen from the scenario seed with an isolated RNG stream, so tiles match each other while scenarios differ (the domain-randomization knob).

**Not done (deliberate first stage)**: intersection corners get no sidewalk pieces (each road's sidewalks stop where its lanes stop, leaving a ~3m gap at every corner, and the intersection centre is just ground asphalt); lane geometry (14m of pavement per road, 2 lanes each way) is not snapped to Epic's real 19/27/37m classes and the real `Kit_City_Road` tiles, crosswalks and lane paint are not used yet; painted (red/white/yellow) curb variants unused.

### [RESOLVED] Per-instance mesh scale is now supported end to end
The real CitySample data needs it: every real curb is placed at scale (1, -0.75, 0.75) (a mirror plus a shrink), roads and sidewalks stretch their last piece to fit a run, and about a third of the walls in several building families are non-uniformly scaled. `FacadePiece` gained an optional `scale` (three floats along the mesh's OWN local axes; a negative component mirrors), `_facade_piece_to_asset_json` emits `"scale"` only when set (so existing payloads are byte-identical), `FScenarioAssetData` gained `Scale`, `ParseAssetData` reads the optional `"scale"` array (three numbers, otherwise the entry is rejected; deliberately NOT run through the Y-flip coordinate conversion, since it is a local-axis quantity) and `UVehicleActorSpawner::SpawnVehicle` applies it with `SetActorScale3D`. Verified live: four copies of one wall (unscaled, y x1.6, mirrored y x-1, and y x-0.75 with z x0.75) render as expected, including the mirrored piece showing a correct face. This unblocks the real curbs, the road/sidewalk kits and the building families that rely on stretched walls; none of those use it yet.

### [RESOLVED, one artifact left] Every frame showed the engine template's checkerboard floor and desert hills
The project's default map is the engine's `OpenWorld` template (`GameDefaultMap=/Engine/Maps/Templates/OpenWorld`, no `.umap` of our own): its Landscape uses `WorldGridMaterial`, which is the checkerboard, plus bare desert hills. Measured against Epic's City Sample levels (headless read-only query): City Sample builds its environment from a sunset-photo sky dome, one low warm sun, exponential height fog, four post-process volumes and Houdini-generated ground, none of which is directly reusable for our generated scenarios (its sky is a fixed photo, its ground is procedural), while our template's SkyAtmosphere and clouds already look real and can vary by time of day.

**What was built** (`src/procedural/environment.py`, `ProceduralScenarioLoader::ApplyEnvironment`, `serialize_scenario(result, environment)`): a scenario payload may carry an `"environment"` object. The plugin then hides the template terrain (show flag plus every Landscape/StaticMeshActor actor, before our own assets spawn), retunes the existing sun angle, exponential height fog and adds an unbound post-process volume (exposure bias, saturation). A large ground quad is added through the normal mesh path with a new `"ground"` material tag mapped to City Sample's already-migrated matte parking-lot asphalt (`M_Asphalt_Master_Inst_ParkingLots`), just below the z=0 road strips. Values started from City Sample's (fog falloff 0.07, warm low sun) and were tuned by eye: City Sample's exact grade (exposure bias -1.0, 4500K sun, green-tinted gain) gave a dark teal cast under our lighting, so the defaults are a milder grade (exposure 0, saturation 0.95). Sun intensity is deliberately left at the template value (City Sample's 2000 belongs to its own exposure setup). `bin/send_scenario_to_ue5.py` sends the default environment; every field is a plain number, ready to become a domain-randomization knob later.

**Verified live** with a real generated 57-building `urban_dense` city: no checkerboard, matte textured asphalt ground to a flat horizon under the real sky, natural warm lighting, in aerial and street-level shots.

**Still a real artifact**: pale, wavy ribbons at the far horizon (thin slivers of the template's hills). They survive hiding 46 template actors, the Landscape show flag and a much denser fog, so they are not ordinary landscape actors or fog-affected. Not investigated further (cause unknown). Separately, the real-asphalt road strips still look glossy like water and the buildings are open-topped; both are already tracked (roads are the next planned work).

### [REFERENCE] Building facade tiling is DONE and verified -- read this before touching `building_facade.py` again
This entry is a quick-reference index for the three detailed entries directly below it (kept in full per this file's own "never delete a closed entry" rule) -- read this one first, then dig into the others only if you need the specific real measurements/evidence trail.

**Current, final state (as of the three entries below)**: buildings tile real City Sample modular kit pieces into flush, correctly-closed, correctly-oriented rectangles, with no visible gap or seam at any corner or along any wall run, live-screenshot-confirmed and covered by geometric-invariant unit tests. This was hard-won across several sessions of real ground-truth investigation (see below) -- do not casually change any constant or rule in `building_facade.py`/`building_placement.py`/`city_sample_assets.py` without re-reading the full evidence trail first, or this problem will very likely come back.

**Per real vertex**: one plain `corner_asset_path` piece, position = the true rectangle vertex exactly (no offset), rendered rotation = the edge-starting-there tiling rotation plus one extra quarter turn (the `CornerEx` mesh's own local orientation convention).

**Per edge, between that corner and the next one**: `wall_asset_path` pieces tiled every `FACADE_WALL_MODULE_METERS` (4.5m) starting `FACADE_CORNER_TO_FIRST_WALL_METERS` (1.5m) from the vertex, rendered rotation = the tiling rotation plus one extra half turn (the wall mesh's own local orientation convention, decoupled from the position math which uses the un-flipped rotation), with one `column_asset_path` pilaster piece after every wall except the last on that edge, `FACADE_WALL_REAL_WIDTH_METERS` (3.25m) further along.

**Every one of these six numbers/rules traces to a specific real measurement** in the actual CitySample project (Houdini BDF config, the real per-instance point cloud, or a hand-placed reference assembly) or a specific falsifiable live UE5 screenshot test -- never guessed. See `src/procedural/building_facade.py`'s and `src/procedural/building_placement.py`'s own module docstrings for the exact real numbers and sources, restated inline next to the code they justify (the most convenient reference for day-to-day work); see the three entries immediately below for the full historical debugging narrative (what was wrong, how it was found, in what order) if you need it.

**Where the numbers live now**: on `BuildingKit` (one floor style: asset paths, `wall_width_m`, `column_width_m`, `corner_to_first_wall_m`, `floor_height_m`, and the mesh-local `wall_yaw_offset_rad`/`corner_yaw_offset_rad`) and `BuildingStyle` (an ordered stack of kits, floor `i` uses `levels[i]`, the last repeats) in `city_sample_assets.py`. `BuildingPlacementGenerator` and `generate_building_facade_pieces` take a `BuildingStyle` (default `DEFAULT_BUILDING_STYLE`, CHA). Levels of one style must share a horizontal grid (enforced at construction); only floor heights may differ. The CHA style is now `CHA_L1` (5.0m ground floor) then `CHA_L2`..`CHA_L6` (3.0m each, heights and the shared 3.25/1.25/1.5 grid read from `CHA_primary.bdf`); L6 repeats for taller buildings, matching its BDF `Repeat=1` and the real point cloud (L6 x24). Height quantization rounds up to a real stack height but never past `config.building_heights[1]` (real stack heights are 5+3n, not multiples of one number). Live-verified (6-floor 19.5m x 15m x 20m building, two opposite corner views): correct exterior facades on every floor, storefront ground floor, flush closed rim. The L2-L6 yaw offsets (pi, pi/2) reuse L1's on point-cloud evidence and looked correct in those screenshots; the entrance pieces (L1, L2 only) are still never emitted, and BDF level-2/3 `P2` thin columns are not placed.

**Edge-length rule (corrected)**: real edges reserve one corner reach at BOTH ends -- the last wall ends exactly `corner_to_first_wall_m` short of the far vertex (measured on 48/48 real CHA and CHH edges, zero error), so an edge with N walls is `2C + N*W + (N-1)*P` long (`BuildingStyle.edge_length_for_wall_count`). The earlier `C + N*(W+P)` overlapped the far corner by 0.25m for CHA (invisible) and would be 2.25m off for CHH. Footprint quantization and wall counting both use the exact formula now; live close-up of a corner confirmed flush.

**Family evidence (point-cloud + BDF read-only survey, 4 real buildings per family)**: best fits for our no-scale model are **CHH L1-L4** (wall 1.25 + "column" 3.25 = Wall_01/Wall_02 alternating, C 1.0, heights 3.25/2.25/3.75/4.25 with L4 repeating; 12% of walls scaled, 1.5% interior) and **SFA L1-L5** (wall 3.25, no columns, C 1.5, heights 12.75/7.5/11.25/3.75 with L5 repeating; needs an optional column). CHE L1-L4 is a partial fit (43% scaled). Poor fits (mostly scaled/varied walls): CHD, CHF, CHG, CHI, NYG, CHB, CHC, NYA; CHJ is not in the point cloud. Yaw deltas (corner 270 / wall 270 vs edge direction) match CHA for CHH, SFA and CHE L1-L4, so our offsets should carry over, but each new kit still needs a live screenshot.

**Styles wired so far**: `CHA` (L1 5.0m ground floor, L2-L6 at 3.0m, L6 repeats) and `CHH` (L1-L4 at 3.25/2.25/3.75/4.25m, L4 repeats; corner reach 1.0m; "wall" = `Wall_01` 1.25m at both ends of every edge, "column" = `Wall_02` 3.25m between them, per the BDF grammar `C1|W1|(W2-W1)*|W2|(W1-W2)*|W1|C1`). Each building draws one style at random (`Building.style_name`). CHH was live-verified with a 10-floor, 39m tower next to a 10-floor CHA tower: bay-window/stone-pier facade with a storefront base, bays projecting outward, flush corners, clearly distinct from CHA. CHH reuses CHA's yaw offsets (pi, pi/2); the screenshots looked correct, but only from a few angles. To wire the next family use `_family_kit` in `city_sample_assets.py`. When testing, use tall buildings (10+ floors): they exercise the repeating top level and every floor type.

**SFA and the CHA crown (added later)**: `SFA` (L1-L5, floors 12.75/7.5/11.25/3.75/3.75m, L5 repeats; wall 3.25m, corner reach 1.5m, NO columns -- `column_asset_path` is optional and `column_width_m` is 0; mesh names use an unpadded level `SM_BLDG_SFA_L1_A_...`, unlike CH's `L01`). `CHA` now has a crown: `BuildingStyle.top_levels` (CHA L7-L10, heights 2.75/3.0/3.0/3.0) sit on top of buildings with at least `len(levels) + len(top_levels)` = 10 floors, with extra height filled by repeats of L6; shorter buildings show no crown (matches the point cloud: buildings 5 and 9 are L1-L5, L6 x N, L7-L10; building 8 is L1-L5 only; the exact minimum height for a crown is inferred). Styles whose one-floor height exceeds `config.building_heights[1]` are skipped (SFA's 12.75m ground floor cannot appear under the parking_lot 10m cap). Live-verified with a 16-floor CHA tower (visible crown with arched windows and cornice) and a 9-floor SFA tower (tall dark-pier ground floor, shorter second floor, taller third floor, flush corners, outward-facing windows). SFA renders as beige painted stone, not red brick (the red-brick materials belong to other SFA levels). Every kit's asset paths were checked to exist on disk (19 kits, 0 missing).

**Checklist to add a new kit/level** (never skip a step; every value needs cited evidence):
1. Migrate the kit's meshes, materials and textures with Epic's Migrate tool (see the material-migration entries below for the precedent).
2. Read the kit's BDF `Mod_Dim` (wall W1, column P1, corner C_E) and `Levels[N].Height`; confirm against real point-cloud spacing for that kit (wall pitch, corner-to-first-wall).
3. Add a `BuildingKit` with those numbers; put it in a `BuildingStyle` in the right level order.
4. Confirm the two mesh-local yaw offsets with a LIVE screenshot (marker at the building center for wall facing; top-down for corner trim). CHA L2-L6 were screenshot-checked with CHA_L1's (pi, pi/2). Point-cloud yaw deltas suggest CHA L7-L11 and other families match too, but that is inference until screenshotted.
5. Add or extend unit tests, run the full suite and lint, update this entry.

**Real per-level evidence (read-only inventory, CitySample point cloud + BDFs)**: Epic uses `CHA_L1` once as the 5.0m ground floor, then `L2`..`L11` (mostly 3.0m) above; floor Z-steps match BDF heights exactly (CHA 209/209). `L1`..`L11` share the 3.25/1.5/1.25 grid; `L12`+ change it. Not yet determined: the exact `LevelsGrammar`/`Repeat` semantics. About a third of real `CHA_L1` walls (48/152) are Y-scaled 1.02-1.21 (same no-scale-field gap as below).

**Known, deliberately-not-implemented real limitation**: one real CitySample building variant (no entrances) non-uniformly SCALES its wall modules to fill an edge with zero remainder instead of using fixed-period walls+columns. This project's `FacadePiece`/scenario-serializer convention has no per-instance mesh-scale field, so that variant isn't represented -- a real, flagged gap for a future session, not a silent one.

### [RESOLVED] Buildings were flat textured boxes -- now real modular City Sample facades (walls/corners, tiled), closing into genuine rectangles
**Reopened, then re-investigated from real ground truth (not inference)**, after a user-reported "walls not lined up, corners in the wrong spot" regression, and after this file's own previous entry here turned out to have been marked resolved prematurely. Module spacing, placement convention, AND the corner-to-perpendicular-wall join are now all converged from **real sources found directly in the actual CitySample project** (not this repo's migrated-assets-only copy, and not inferred from mesh bounding boxes, which was tried first and produced wrong values):
1. `Content/Building/HDA/Bldg/BDF/CHA_primary.bdf` -- Epic's own real Houdini building-definition config (plain JSON). Gives the real authored module width for the plain exterior corner (`Mod_Dim=[1.5, 5.0]`).
2. `Content/Building/Library/pointclouds/All_Buildings_Lineup_pc` -- the real per-instance transform database behind Epic's actual generator output (a SQLite-backed point cloud, read directly via the `unreal.PointCloud`/`PointCloudView` Python API in a live Editor Script). Across many real generated buildings: a corner's distance to the first wall of the edge that starts at it (matching its own rotation) is exactly 150cm, matching the BDF exactly; consecutive wall-to-wall spacing along a straight run is a consistent 450cm (larger than the wall mesh's own measured bounding box, 325cm -- a real, deliberate reveal/gap between panels in the actual game, not a bug).
3. `Content/Building/Library/Kit_Ref_Bldg/CHA_Ref_N1` -- a hand-placed reference assembly, independently confirming the 450cm wall spacing and confirming a corner's pivot IS the true rectangle vertex (no pivot offset) with no perpendicular offset for any piece on an edge.

`FACADE_WALL_MODULE_METERS`/`FACADE_CORNER_TO_FIRST_WALL_METERS` in `building_placement.py` and the tiling loop in `building_facade.py` use these real values.

**The corner-to-perpendicular-wall join, previously an unresolved real defect, is now fixed** -- also from real point-cloud evidence, not guessing. A single `CornerEx` piece's own measured local bounds are provably asymmetric (least-squares proof this session: no rigid placement flush-matches both of the two edges meeting at a vertex). The real point cloud showed the actual answer directly: at one real building vertex, Epic's own generator places BOTH `CornerExL` and `CornerExR` at the exact same position, with different rotations -- `CornerExR` matching the edge that starts there (own edge) and `CornerExL` matching the edge that ends there (incoming edge). `generate_building_facade_pieces` now does the same: two stacked corner pieces per vertex instead of one. `BuildingKit` gained `corner_l_asset_path`/`corner_r_asset_path`. Verified live: all 4 corners of a real generated rectangle now show correct, properly-mitered 90-degree L-shaped geometry (previously a disconnected "pinwheel"), with walls correctly closing each edge.

**Real, separate, now-fixed bugs found this session while chasing the above**:
1. A wall piece's own tiling-step offset had a spurious extra `+1` module shift (see `generate_building_facade_pieces`'s inline comment) -- removed, verified against the wall's real measured local Y bounds.
2. `_rotate_2d` (used for every position offset in `building_facade.py`) was rotating by `-rotation_rad` instead of `+rotation_rad` -- conflating "how the mesh visually rotates in UE5" (genuinely `-rotation_rad`, via `ProceduralScenarioLoader.cpp`'s Yaw conversion) with "how a position offset for placing that mesh should be computed" (a different quantity). Found via a precise, falsifiable live test: a corner+wall pair confirmed flush at rotation 0 was rigidly rotated to rotation `-pi/2`; the old (negated) position formula broke the flush join, the corrected (non-negated) one preserved it exactly. This also flips the corner-index-to-rotation formula from `-edge_index * 90°` to `+edge_index * 90°` (re-derived and verified numerically against all 4 real edge directions). Tests `test_corner_r_piece_rotation_matches_its_own_edge_direction`/`test_corner_l_piece_rotation_matches_its_incoming_edge_direction` in `tests/unit/test_building_facade.py` assert the absolute rotation-to-edge-direction mapping for both corner variants -- the older spacing/count tests could not have caught this sign bug, since consecutive-wall spacing stays correct regardless of which absolute direction "forward" is.
3. A single `CornerEx` asset can't cover both edges at a vertex (see above) -- fixed by emitting `CornerExL` + `CornerExR` instead of one `CornerEx`.

**A fourth real bug, found after the above via a different class of live test**: with the corner-join fix in place, a user report ("why is the exterior part of walls and corners facing the inside") led to a dedicated orientation test -- a marker placed at the building's true geometric center, screenshotted top-down. Every wall's window/trim face pointed INWARD, toward that center marker, confirming the wall mesh's decorative face is on the opposite local side from what the position-tiling convention assumed. Fixed by storing `rotation_rad + pi` on each wall `FacadePiece` at construction -- deliberately only on the piece's final, rendered rotation, not on the `direction`/`wall_position` computation feeding it (that position math was independently already correct and would have broken edge closure if flipped too). Re-verified live: the center-marker screenshot now shows every wall facing outward, and a close-up at a corner-wall junction shows no seam/orientation mismatch between the (flipped) wall and the (unflipped) corner pieces, confirming corner pieces did not need the same fix.

**Still a real, accepted v1 limitation**: every floor reusing the same `CHA_L1` kit style (real per-floor variety not yet migrated), and no per-instance mesh SCALE support (see the entry immediately below for why real "no-entrance" City Sample buildings need one and this project doesn't have it yet).

See `src/procedural/building_facade.py`'s own module docstring for the full technical derivation and the precise falsifiable tests/real data that found and fixed all three bugs.

---

### [RESOLVED] Visible top-down gap at every corner turn -- root cause was NOT the corner-to-wall constant; it was two other real, now-fixed modeling errors
**User-reported after live top-down/angled screenshots of a real generated 3-floor building** ("small triangular/wedge-shaped voids at each corner, visible from directly overhead"). The entry above's "1.25m reveal gap ... a real, deliberate Epic design choice, not something to close" turned out to be WRONG -- re-investigated this session from real ground truth, not by guessing at the existing constants.

**Rigorous re-measurement of `All_Buildings_Lineup_pc`** (not the single cherry-picked vertex earlier sessions had used): every real `Kit_Bldg_CHA_L1_A` point across all 4 real buildings that use it (ids 0, 5, 8, 9; 332 real points), grouped into 16 real straight edges and walked corner-to-corner. Two real findings, both with hard numbers:

1. **`FACADE_CORNER_TO_FIRST_WALL_METERS` (1.5m) is exactly correct** -- 16/16 real corner-to-first-owned-edge-wall measurements came back at precisely 150cm, zero exceptions, independent of building size. The corner-to-wall join was never the bug.
2. **The "125cm reveal" is not empty in real Epic buildings -- it is filled by a real Column mesh** (BDF module `P1`, `SM_BLDG_CHA_L01_A_Column_01_N1`, already migrated into `VantageCV_UE5`'s Content). Real Wall->Column->Wall->Column spacing is an exact, zero-exception 325cm/125cm alternation across 128 real column instances and 152 real wall instances (3 of the 4 real buildings measured; matches BDF's `W1` Mod_Dim=3.25m and `P1` Mod_Dim=1.25m exactly). This project's generator was never emitting that Column piece at all -- fixed by adding `BuildingKit.column_asset_path` and emitting one Column between every pair of consecutive walls on an edge (`generate_building_facade_pieces` in `building_facade.py`).
3. **A second, independent real bug, found by checking corner-asset usage FREQUENCY (not just existence) across the same 16 real vertices**: the earlier "every vertex gets a stacked `CornerExL`+`CornerExR` pair" fix (see entry above) was itself based on a single real vertex, generalized without checking how common it actually is. The rigorous re-query found the plain `CornerEx` asset used at 15/16 real vertices, `CornerExR` at only 1/16, `CornerExL` at 0/16, and no real vertex ever stacking two corner pieces. Reverted `generate_building_facade_pieces` back to emitting one plain `corner_asset_path` piece per vertex, matching the real majority. `corner_l_asset_path`/`corner_r_asset_path` are kept on `BuildingKit` (real asset paths) for a future session with enough real samples to determine the rare non-plain case's actual trigger.

**A real, deliberately NOT implemented finding**: the 4th real building (id 8) has no entrances and no columns at all, and its wall-to-wall spacing is non-round (330.31cm / 343.68cm on different edges) -- Epic's Houdini generator non-uniformly SCALES each wall module to exactly fill that edge with zero remainder, for the plain "no entrance" grammar variant (`"C|(W1)*|C"` in the BDF). This project's own generator never emits entrances either, so this is arguably the more faithful real grammar to match -- but doing so needs a per-instance mesh SCALE, which `FacadePiece`/the scenario-serializer asset convention has no field for today. Not added this session (a real architecture change, not something to guess the shape of) -- flagged here for a future session. The Wall+Column fixed-period model implemented instead is real (matches the entrance-grammar's own fixed-period sub-pattern with zero exceptions in 128+152 real samples), just not the only real pattern Epic uses.

**Verified live**: sent a real 4x3-wall-module, 3-floor generated building (using the fixed code) to a running `VantageCV_UE5 -game -d3d11` instance via the existing WebSocket RPC bridge (`UE5Backend`/`LoadProceduralScenario`), then used `DebugMoveCameraTo`/`TakeScreenshot` for a top-down shot and two angled/overhead corner close-ups. All three show a continuous, seamless closed rectangle -- no visible wedge/void at any of the 4 corners, and the Column pieces are visible as the vertical pilaster strips between window bays in the angled close-up, exactly where real Epic buildings place them. Screenshots not committed (this session's own scratchpad only, per project convention).

See `src/procedural/building_facade.py`'s and `src/procedural/building_placement.py`'s own module docstrings for the full real numbers (every real building/edge, not just an average).

---

### [RESOLVED] Corner piece's own outer trim didn't wrap flush around the true vertex -- the last visible seam
With the column fix above in place, a live top-down/angled screenshot of the same real 3-floor generated building still showed one remaining visible defect: the corner piece's outer trim did not wrap flush around the true rectangle vertex against either adjoining wall -- a real, user-reported seam ("the corners are the only thing that's not perfect ... rotate all corners 90 degrees").

Applied and verified live rather than assumed: added one extra quarter turn (`_QUARTER_TURN_RAD`) to the corner `FacadePiece`'s STORED (rendered) `rotation_rad` in `generate_building_facade_pieces` (`building_facade.py`) -- the same class of fix as the earlier wall `+ math.pi` flip, just a different real offset for the `CornerEx` mesh's own local orientation convention. Since a corner piece's position is always exactly the true vertex (no separate `direction`/position computation depending on rotation, unlike a wall), this offset is safe to apply directly with nothing left to keep unflipped. A fresh top-down screenshot after the change shows the corner's trim now wrapping the vertex exactly flush against both adjoining walls (previously a visible gap on one side), and the angled shot shows a genuinely seamless corner join matching real Epic architecture.

`test_corner_piece_rotation_matches_its_own_edge_direction` in `tests/unit/test_building_facade.py` updated to subtract the quarter turn back out before checking the underlying own-edge-tiling-rotation invariant, so it still asserts the real geometric fact (not just re-encoding whatever the code currently does).

Full suite (485 tests) and lint (`black`/`isort`/`pylint` 10/10/`mypy --strict`) clean after this change.

<details>
<summary>Original (superseded) resolution writeup</summary>
Follow-up to the material-wiring entry below: buildings had real brick/concrete/glass materials but no facade detail (no windows, floors, or trim) -- the single biggest remaining gap toward "looks like a real video game city." Heavily researched (4 parallel research passes) whether UE5 5.4.4's PCG framework could close this gap: **it can't, cleanly** -- PCG is still beta at 5.4, and the real shape-grammar building-generation tooling only exists in Epic's separate 5.7/5.8 City Sample rebuild. Real alternative found instead: City Sample ships genuine modular building-kit pieces (`Kit_Bldg_CHA_L1_A`: wall, corner, entrance, column -- individual static meshes meant to be tiled edge-to-edge, not baked into one asset), confirmed via direct inspection of the real CitySample content, not assumed.

**Real proof-of-concept before writing any implementation code** (per explicit instruction to be confident before implementing): added a new debug RPC, `GetStaticMeshBounds` (`unreal_plugin/.../Networking/SyntheticDataGenRpcSubsystem.cpp`), to measure real asset dimensions from the live engine rather than guessing (wall/entrance: 325cm wide x 500cm tall, pivot at one width-edge; corner: ~178cm x 178cm footprint). Spawned 4 wall pieces via pure position math (no PCG, no Houdini) -- tiled seamlessly, confirmed via live screenshot: real windows, real concrete trim, no gaps. Then placed corner pieces at a rectangle's 4 corners with a 90-degrees-per-corner rotation scheme -- confirmed correct L-shaped corner geometry live.

**Implementation**: `building_placement.py` gained `FACADE_WALL_MODULE_METERS`/`FACADE_CORNER_MODULE_METERS`/`FACADE_FLOOR_HEIGHT_METERS` and quantizes every building's sampled width/depth/height up to an exact module multiple at generation time -- same precedent as the existing road-grid quantization fix (see that entry below): a building whose dimensions don't land on exact wall/corner/floor multiples can't be tiled without a visible gap or overlap, so the fix belongs in the generator, not a rendering workaround. New `building_facade.py`: `generate_building_facade_pieces` is a pure, deterministic function (no RNG) that tiles a quantized `Building`'s perimeter, per floor, with real wall/corner pieces, derived directly from the confirmed-live rotation/tiling-direction behavior above. `city_sample_assets.py` gained `BuildingKit`/`BUILDING_KITS` (one real migrated kit so far: `CHA_L1`). Buildings stop feeding `MeshFactory.build_building_mesh` into `ScenarioResult.meshes` (that function stays, used only by its own tests/validator -- same precedent as `build_vehicle_mesh`); `ScenarioResult` gained `building_facade_pieces`, serialized by `scenario_serializer.py` as new `"static_asset"` `"assets"` entries (no `part_paths` -- each piece is its own independent spawn, unlike a vehicle body+parts group). Ground truth is unaffected -- `extract_bboxes_3d`/`ScenarioValidator._validate_buildings` already derive building boxes from `Building.aabb`/`.height` directly, never from mesh/piece geometry. C++: `ProceduralScenarioLoader.cpp`'s category dispatch broadened to accept `"static_asset"` alongside `"vehicle"`, routing through the same `UVehicleActorSpawner::SpawnVehicle` (already handles an empty `PartPaths` list gracefully).

**Real bug found and fixed during full-scenario live verification, not shipped broken**: the entrance piece (`SM_BLDG_CHA_L01_A_Entrance_01_N1`) renders with a visibly wrong flat gold/tan material (not the glass/concrete finish every wall/corner piece correctly shows) -- confirmed isolated to that one asset by spawning it alone, and confirmed *not* a logged material-resolution failure (no "Missing Material"/"failed to load" warning), so the real cause (a genuine unfinished/construction-state asset variant vs. an incomplete migration) isn't diagnosed. Shipping a visibly broken entrance looked worse than a building with no distinct entrance at all -- `generate_building_facade_pieces` deliberately never selects `BuildingKit.entrance_asset_path` (real, documented v1 limitation, not silently dropped); every wall slot including the ground floor uses the plain wall piece. Re-verified after this fix at both single-building and full 24-building dense-scenario scale: no broken/gold pieces anywhere, consistent real windows/trim across every building.

**Also a real, accepted v1 limitation**: every floor of a multi-floor building reuses the same `CHA_L1` kit -- City Sample ships many more floor styles (`Kit_Bldg_CHA_L2_A` through `L21_A`) for real per-floor variety, deliberately not migrated yet. No separate roof cap piece either -- the wall module's own top coping forms the roofline; open-top from directly above is accepted (street-level AV camera framing won't see it).

**Real, separate bug found and fixed along the way**: sending a real scenario with building facade pieces populated grew the JSON "assets" payload past the `websockets` library's default 1 MiB per-message cap (`websockets.exceptions.PayloadTooBig`), affecting both the real `UE5Backend` client and its own test mock servers (they share the same client-side default). Fixed by passing `max_size=None` to both `websockets.connect` (`src/ue5/backend.py`) and every test's `websockets.serve` call -- a local, trusted connection to our own UE5 plugin, not an arbitrary untrusted server, so the untrusted-server-sized default doesn't apply.

Full suite (483 tests) and lint clean throughout.

</details>

### [RESOLVED] Building/road mesh sections never applied a real material -- always rendered as UE5's default flat material
`ScenarioMeshBuilder::BuildMeshSection` built real geometry/UVs/tangents but never called `SetMaterial` at all -- every building and road rendered as UE5's default gray/checker material regardless of its `Mesh.material` tag (`"brick"`, `"asphalt"`, etc.), the biggest remaining visual gap now that vehicles are fully assembled, textured, and verified (see the vehicle entries above).

**Real investigation, not guessing**: searched City Sample's real content for candidate materials per tag, then verified each candidate's own dependencies via the same binary-string-decoding technique used for the earlier vehicle paint fix -- confirmed a real, self-contained `Content/Building/Material/` library exists (base master material + per-category `MI_Bldg_*` instances: Brick, Wood, Glass, Concrete, Metal, Paint) and a real `Content/Road/Material/MI/M_Asphalt_Master_Inst` for asphalt. Unlike the earlier single-file Traffic plugin fix, these have real multi-level dependency chains (several `/Game/Material/...`/`/Game/Textures/...`/`/Game/Megascans/...` references each) -- confirmed by direct inspection, not assumed shallow. Manually hand-copying files based on a regex-extracted dependency list carries real risk of missing a binary-only (non-string) object reference and producing broken/missing textures, unlike the earlier single-dependency-free Traffic file -- so migrating the real assets is deliberately left to Epic's own Editor "Migrate" tool (which resolves the complete dependency graph correctly), the same category of manual step already documented for Vehicle content.

**Implementation, verified independently of the still-pending migration**: `configs/material_tags.json` -- single source of truth for every material tag string `src/procedural/mesh_factory.py`/`building_placement.py` can emit, each mapped to a real, dependency-checked City Sample asset path (chosen assets: `MI_Bldg_BrickOffset_Red`, `MI_Bldg_Wood_Cedar`, `MI_Bldg_PaintedStone_Beige` for stucco -- no dedicated stucco asset exists in the kit, a painted-smooth-stone finish is the closest real visual match --, `MI_Bldg_Concrete_Dirty`, `MI_Bldg_glass_opaque`, `MI_Bldg_Metal_Brushed`, `M_Asphalt_Master_Inst`; the two dead/deferred `vehicle_paint`/`pedestrian` tags map to generic `MI_Bldg_PaintedMetal_*` instances as reasonable placeholders, not dedicated assets, since neither feeds the real live pipeline yet). `tests/unit/test_material_tags_coverage.py` (new, 4 tests) asserts every tag `BUILDING_MATERIALS_BY_TYPE` and `MeshFactory`'s own fixed-string tags can emit has a real, `/Game/`-rooted entry. C++: new `FMaterialResolver` (`unreal_plugin/.../ProceduralMesh/MaterialResolver.{h,cpp}`) is a small, hand-kept-in-sync `TMap<FString, FString>` (tag -> asset path, mirroring `material_tags.json`'s own entries -- deliberately not parsed from that JSON at runtime or cross-language-codegenned, out of proportion for 9 entries) with a cached `LoadObject` lookup; `ScenarioMeshBuilder::BuildMeshSection` now calls it and applies the resolved material via `SetMaterial(0, ...)` when found.

**Verified via a real live session, not assumed**: rebuilt, relaunched, sent a real box mesh tagged `"brick"` (deliberately before migrating the real asset, to test the fail-soft path) -- the engine log showed exactly the expected `LogMaterialResolver: Warning: Resolve: failed to load material ... has it been migrated into this project?` warning, and a screenshot confirmed the mesh still rendered correctly with the default fallback material, no crash. This confirms the resolver wiring itself is correct end-to-end; real textured output still requires the one-time manual migration below.

**Manual step still required** (same category as the existing Vehicle/Traffic migration steps): in the UE5 Editor (not `-game` standalone -- Migrate needs the Content Browser), open `CitySample`, select `Content/Building/Material/M_Bldg_Base.uasset` plus the six chosen `MI_Bldg_*` instances (`Brick/MI_Bldg_BrickOffset_Red`, `Wood/MI_Bldg_Wood_Cedar`, `Paint/MI_Bldg_PaintedStone_Beige`, `Concrete/MI_Bldg_Concrete_Dirty`, `Glass/MI_Bldg_glass_opaque`, `Metal/MI_Bldg_Metal_Brushed`, `Paint/MI_Bldg_PaintedMetal_Red`, `Paint/MI_Bldg_PaintedMetal_Grey`) and `Content/Road/Material/MI/M_Asphalt_Master_Inst.uasset`, right-click -> Asset Actions -> Migrate, and point the destination at `VantageCV_UE5`'s `Content` folder (Migrate resolves and copies the complete real dependency graph automatically, unlike a manual file-by-file copy).

### [RESOLVED] Debug/overview camera pawn could cast a visible shadow onto generated content -- misread as a broken vehicle texture
User reported a specific police vehicle (`vehCar_vehicle13`) looking "glitched," with jagged dark patches on the hood/roof. Investigated heavily per explicit instruction to be confident before changing anything, rather than guessing.

**Ruled out, with real evidence, not assumed**: not a texture streaming race (pattern persisted unchanged after a 20s wait with no scenario reload); not a broken/misassigned material or UV data (a different viewing angle on the exact same vehicle showed the same panel completely clean, and a taxi parked nearby showed a pixel-crisp "TAXI" livery decal, proving the livery/texture pipeline itself works); not UE5 Contact Shadows (tested directly by setting `bCastContactShadow = false` on every vehicle component -- zero visual change, reverted since it did nothing).

**Real root cause, confirmed by two direct tests**: it is the vehicle's own ordinary real-time directional-light shadow (elongated by a low sun angle in this scene, and made visually complex by the roof-mounted light bar/antennas), not any kind of texture or material defect. Confirmed by (1) moving the vehicle 2000m away while keeping the camera fixed on the same spot -- the "glitch" vanished entirely (clean empty ground); (2) rotating the same vehicle 90 degrees in place -- the shadow's shape stayed fixed in world-space direction instead of rotating with the vehicle, the signature of a real directional-light shadow rather than anything baked into the mesh. From a normal (non-overhead, non-close) camera angle representative of real capture framing, the shadow does not fall across the vehicle at all. No vehicle-spawning/material code needed to change for this part.

**Real, separate bug found and fixed along the way**: both `USyntheticDataGenRpcSubsystem::HandleRpcRequest`'s `DebugMoveCameraTo` handler and `ProceduralScenarioLoader.cpp`'s `RepositionOverviewCamera` repurpose the level's actual gameplay Pawn (a visible character mesh) as a flying camera. Confirmed via a real screenshot that `SetActorHiddenInGame(true)` alone does **not** stop that pawn's mesh from casting a shadow into the scene -- third-person/first-person character meshes commonly have `bCastHiddenShadow = true` set explicitly (so a first-person view that hides its own body mesh still shows that body's shadow in the world), which is exactly this project's default Pawn. **Fixed**: added `HideActorAndItsShadow()` in both files, which hides the pawn AND explicitly calls `SetCastShadow(false)` on every one of its `UPrimitiveComponent`s. This was not the cause of the reported vehicle13 issue (the pawn was never near it in the decisive tests), but it is a real, verified defect in the debug/overview camera tooling in its own right -- an invisible flying camera pawn should never be able to visibly affect the scene it's observing -- so it's kept as a genuine fix, not spec creep.

Also confirmed while investigating: `vehCar_vehicle13`'s black-front/white-rear livery split (boundary at the B-pillar, not a horizontal roof band) is the actual authored City Sample police livery texture, not corrupted or partially-loaded data -- a design choice, not a bug. Separately, glossy clear-coat car paint strongly reflects the sky at near-overhead viewing angles, which can make a genuinely black roof look white in a top-down screenshot; this is real specular reflection, not incorrect base color.

### [RESOLVED] Vehicles were body-shell-only -- now fully assembled (wheels, doors, glass, interior, steering wheel)
Follow-up to the body-shell-only limitation the previous vehicle-visibility entry deliberately left open. Each vehicle's real wheel/door/glass/interior/steering-wheel static meshes exist as separate assets alongside `SM_Frame_<name>` -- confirmed by direct inspection of all 14 vehicle folders, not assumed uniform (some genuinely differ: the two dual-rear-axle trucks have 6 wheels via an extra "Axel3" pair; the trailer has 6 wheels across 3 axles and no doors/glass/interior at all, since it has no cab; the bus has 4 wheels and no doors modeled this way).

**Real finding, confirmed via a live test, not assumed**: every part's own mesh data is pre-modeled in its final assembled position already relative to the vehicle's shared origin -- a common modular-vehicle-kit convention. Spawning a part at the exact same position/rotation as the body (zero offset, no per-part socket/attachment math) produces a correctly assembled vehicle. Confirmed via a sequence of real screenshots: one wheel alone landed exactly at the front-left corner; all 4 wheels + 2 doors together produced a clean, correctly assembled car with no seams or duplication; adding the glass mesh showed correctly placed windows; adding the interior mesh showed a real seat visible through the windshield.

**Real bug found and fixed during this same pass**: an earlier manual survey of which vehicles have headlight/taillight meshes wrongly included `vehCar_vehicle03` -- caught via a real live spawn failure (`"failed to load static mesh"` for all 4 headlight/taillight paths), then confirmed on disk that vehicle03 genuinely has none. Lesson: always trust a live spawn failure over an earlier manual survey, and re-verify rather than assume consistency across superficially-similar assets.

**Implementation**: `city_sample_assets.py` gained `VEHICLE_PART_PATHS: Dict[str, List[str]]`, keyed by vehicle folder name (not body-type category, since every vehicle's real part list is genuinely its own), listing every real additional part for that vehicle. `scenario_serializer.py`'s `_vehicle_to_asset_json` derives the vehicle's folder from its own body `asset_path` and looks up its part list, embedding it as a new `"part_paths"` field on each vehicle's `"assets"` entry. `FScenarioAssetData` (C++) gained a `PartPaths` array; `ParseAssetData` parses it (optional -- missing/absent is treated as empty, not a parse failure); `UVehicleActorSpawner::SpawnVehicle` now loads each part as its own `UStaticMeshComponent`, attached to the body's root component with `KeepRelativeTransform` (not `KeepWorldTransform` -- a real, documented near-bug: `KeepWorldTransform` would have preserved each part's freshly-created world-origin transform instead of moving it onto the vehicle, since a new component's relative transform defaults to identity and identity-relative-to-the-body is exactly what's needed).

**Verified end-to-end through the real pipeline** (not just hand-crafted test JSON): all 14 vehicles' full part sets (173 total static meshes before the headlight/taillight fix, 169 after) spawned via a raw test scenario with 0 skips; a real generated scenario sent through `bin/send_scenario_to_ue5.py` (the actual `generate_scenario` -> `serialize_scenario` -> RPC path) also spawned all vehicles' full assemblies with 0 skips, confirmed via engine log and a real screenshot.

Brake pads and the visible engine were deliberately not added (mostly hidden behind wheel rims / under a closed hood -- low visual payoff for the added per-vehicle catalog complexity); `vehCar_vehicle13`'s unique turn-signal meshes were added since they were already being touched, `SM_Wheel_MotionBlur*`/`SM_MotionBlur_*` meshes were deliberately excluded (motion-blur effect geometry, meaningless for a frozen-frame static scene).

### [RESOLVED] Vehicle paint materials/textures -- real root cause found and fixed, not the MassTraffic plugin dependency it looked like
The previous entry left this open as a "deeper City Sample plugin-dependency problem" with "no publicly documented fix" (per a dedicated background research pass). Heavily re-investigated on the user's explicit request to be confident before implementing anything -- and the real root cause turned out to be narrower and genuinely fixable, not the large MassTraffic AI-traffic-system dependency it appeared to be.

**Real investigation, not another guess**: the engine log's actual error was `Failed to load '/Traffic/MaterialFunctions/MF_UnpackTrafficVehicleInstanceCustomData': Can't find file` -- a missing *content mount point*, not a missing C++ class. Decoded the real `.uasset` binary directly (parsed for embedded ASCII strings) to check what it actually depends on: its only external references are `/Script/CoreUObject`, `/Script/Engine`, and `/Script/UnrealEd` -- all standard engine packages present in any UE5 project, not `/Script/MassTraffic` or anything Traffic-plugin-specific. It uses only two built-in material expression node types (`MaterialExpressionCustom` for raw HLSL, `MaterialExpressionPerInstanceCustomData` for reading per-instance GPU data) -- both core Engine classes, not anything MassTraffic's own C++ source defines. Also confirmed the entire real Traffic plugin's `Content/` folder contains exactly this one file -- nothing else. Conclusion: this material function is pure content that merely happens to be organized inside the Traffic plugin's folder; it has no genuine functional dependency on MassTraffic's actual C++ traffic-AI system at all.

**Fix**: created a new, minimal, *content-only* plugin also named `Traffic` (matching the mount point City Sample's existing, already-migrated material functions already hard-reference -- `VehicleImperfection`, `DynamicVehicleDamage`, `VehicleEmissive` -- so no material graph editing was needed at all) with no `Modules` section in its `.uplugin` (so it requires no C++ compilation, unlike the real MassTraffic plugin), containing just the one copied `.uasset` file at the matching relative path (`Content/MaterialFunctions/MF_UnpackTrafficVehicleInstanceCustomData.uasset`). Enabled it in `VantageCV_UE5.uproject`. This is deliberately **not** a copy of Epic's real Traffic/MassTraffic plugin -- no Mass AI traffic simulation, no `ChaosVehiclesPlugin`/`ZoneGraph`/`MassAI` dependency, no `Source/` at all.

**Verified, not assumed**: relaunched (no C++ rebuild needed -- the new plugin has no modules), and the "Missing Material Function"/"Failed to compile Material" warnings that previously appeared for every vehicle material dropped to zero across the entire session log. A single-vehicle screenshot showed a real, solid, uniform paint color replacing the "no material" checkerboard pattern. A follow-up 5-vehicle (sedan x2, SUV, truck, bus), full-part-assembly screenshot showed real distinct paint colors (cream/white body paint, a genuine red taillight lens, black wheel/tire rubber) -- clear evidence of real functioning per-slot materials, not a uniform fallback.

The authored `.uplugin` descriptor is committed at `unreal_plugin/Traffic/Traffic.uplugin` (small, deliberately-written text, unlike bulk migrated binary content which stays untracked per this project's existing convention). **Manual step still required** to reproduce on a fresh clone/setup (same category as the vehicle asset migration): copy `unreal_plugin/Traffic/Traffic.uplugin` into `VantageCV_UE5/Plugins/Traffic/Traffic.uplugin`, copy `CitySample/Plugins/Traffic/Content/MaterialFunctions/MF_UnpackTrafficVehicleInstanceCustomData.uasset` into `VantageCV_UE5/Plugins/Traffic/Content/MaterialFunctions/` (same relative path), and add `{"Name": "Traffic", "Enabled": true}` to `VantageCV_UE5.uproject`'s `"Plugins"` array.

### [DEFERRED] Road network is a plain uniform grid -- reasonable for this stage, real next-step identified via research on how AV/PCG companies actually do it
The user asked, alongside the three-bugs dogfooding report below, whether the road-network generation approach ("is this smart, and how do real PCG/AV companies do it") should be reconsidered rather than just patched. Researched with real citations, not general-knowledge claims:

- **CARLA**: maps are hand-authored (typically via RoadRunner) and exported to the ASAM OpenDRIVE standard; CARLA 0.9.15 added a pipeline that imports real **OpenStreetMap** data and decorates it, rather than generating synthetic road topology from scratch. (`carla.readthedocs.io/tuto_content_authoring_maps`, `carla.readthedocs.io/adv_opendrive`)
- **NVIDIA DRIVE Sim/Omniverse**: public docs describe Omniverse Replicator (domain randomization, sensor sim, ground truth) built on top of existing scenes -- no public source describes NVIDIA algorithmically generating road topology from scratch. (`blogs.nvidia.com/drive-sim-replicator`, `docs.omniverse.nvidia.com/simready`)
- **Applied Intuition / Waabi / Parallel Domain**: all three favor real-world-derived environments -- log-based/real-driving-log synthetic conversion (Applied Intuition), agent-behavior modeling on top of existing road graphs rather than generating the graph (Waabi's MixSim), and a stated shift toward NeRF/Gaussian-splat reconstruction of captured real environments over pure procedural generation (Parallel Domain).
- **Academic/OSS procedural city generation**: the standard *procedural* techniques when not hand-authoring or importing real maps are grammar-based/L-system generation (CityEngine's foundation) and tensor-field-based street generation (major/minor eigenvector fields traced into organic, non-orthogonal streamlines) -- both produce varied block sizes and non-90-degree intersections, unlike a uniform grid.

**Verdict**: none of the real AV-specific companies researched rely on a plain synthetic grid for their flagship realism story -- they prefer real-world map/log import or reconstruction. That said, **a plain uniform grid is a reasonable, known simplification for an early-stage/solo project** (matches how even CARLA's own pipeline defaults for un-mapped areas, and how simplified-geometry synthetic segmentation datasets like SYNTHIA/Synscapes work) -- not a mistake to feel behind on, but a known weak point for perception-training diversity if left as the permanent end state (real road networks vary block size, include T-intersections/curves/non-90-degree angles that affect the scale/occlusion distributions a model sees in training).

**Identified next-highest-value step** (deliberately NOT implemented yet -- a real scope decision, not an oversight): variable block spacing and occasional T-junctions *within the existing grid framework*, before considering either OpenStreetMap import (the industry-favored path, used by CARLA itself, cheaper than tensor-field synthesis, gives real-world-validated topology for free) or a full tensor-field rewrite. Also worth a later look: the CityTopia dataset (11 cities, built on the same UE5 City Sample assets this project already imports) as a directly comparable precedent.

### [RESOLVED] Live-session dogfooding found three real bugs: vehicles invisible, inconsistent road widths, thin leftover blocks
User watched a live standalone UE5 session cycling through several procedurally generated city layouts (via `bin/send_scenario_to_ue5.py`, Phase 1's real vehicle-spawn path) and reported three concrete visual problems. All three were root-caused against real code and fixed, not guessed at.

1. **Vehicles were invisible -- real bug in `UVehicleActorSpawner::SpawnVehicle`.** `World->SpawnActor<AActor>(AActor::StaticClass(), SpawnTransform, SpawnParams)` spawns a bare `AActor`, which has **zero default subobjects** -- no `RootComponent` exists at spawn time. UE5's `SpawnTransform` argument only takes effect by being applied to a `RootComponent`; with none present, it's silently dropped (not an error, no log warning -- just quietly ignored). The `USkeletalMeshComponent` created and set as root *afterward* then starts at its own default transform (world origin), not at `AssetData.Position/Rotation`. Every spawned vehicle was very likely stacked at world origin (0,0,0), nowhere near the generated city -- explaining why none were visible despite the engine log correctly reporting "spawned N asset(s), skipped 0" every time (the spawn itself succeeded; only the position was wrong). **Fixed**: call `SpawnedActor->SetActorLocationAndRotation(AssetData.Position, AssetData.Rotation)` explicitly after the real root component exists, in `unreal_plugin/.../ActorSpawn/VehicleActorSpawner.cpp`.

2. **Road widths visibly inconsistent -- real, not perceptual.** `RoadNetworkGenerator._assign_road_attributes` sampled `num_lanes` randomly per road (`rng.choice([2,3,4])` for major/long roads), and `lane_topology.py`'s rendered pavement width is `num_lanes * LANE_WIDTH_METERS` -- so roads genuinely rendered at different widths (confirmed via a real generated scenario: 7.0m vs 10.5m per direction). Separately confirmed `RoadEdge.width_meters` (sourced from `config.avg_road_width`) is dead/unused for rendering -- grepped the whole codebase, nothing reads it after `_create_edge_pair` sets it; it was never the actual visual width, just misleading unused metadata. **Fixed**: added `UNIFORM_LANE_COUNT = 2` in `road_network.py`, used for every road regardless of hierarchy -- a deliberate simplification for "this stage of the project" (user's own framing), not a permanent design decision. Road hierarchy (residential/minor/major) and speed limit still vary; only lane count/width is pinned. `width_meters`'s disconnection from real rendered width is a separate, still-open piece of dead metadata, not fixed here (documented, not touched, to avoid unrelated scope creep).

3. **Two same-direction roads separated by a thin sliver of buildings -- real bug in `RoadNetworkGenerator._axis_coords`.** The previous implementation (`np.arange(lo, hi, spacing)` plus an appended `hi`) let the *final* interval on an axis be whatever was left over after fitting as many full-`spacing` steps as possible -- which could be far shorter than every other block on that axis (confirmed via a real generated scenario: spacings of `[134.18, 65.82]` on one axis, a 2x difference; worse cases are possible depending on how the random spacing value happens to divide the bounds extent, down to near-zero in the worst case). **Fixed**: quantized to the nearest whole number of *equal*-width intervals (`num_intervals = round((hi-lo)/spacing)`, then `np.linspace`), so every block on a given axis is now identically sized -- confirmed via re-generating the same scenarios: spacings collapsed to e.g. `[100.0, 100.0]` uniformly. Block size still varies scenario-to-scenario (the sampled `spacing` value still varies within `config.avg_block_size`), just internally consistent within one scenario's grid, matching how a real street grid actually looks.

**Real, expected side-effect of fix #3, not a regression**: `test_different_seeds_produce_different_networks` started failing after the quantization fix, because two seeds whose randomly sampled spacing rounds to the same interval count now produce an *identical* grid by design (confirmed: seeds 42 and 43 collide exactly at this test's fixture bounds/block-size). Rewrote the test to check variety across a spread of 8 seeds rather than any two specific ones, since requiring literally every pairwise seed comparison to differ is incompatible with the (correct) new quantized-grid behavior.

Also added (separately, same dogfooding session, user requested being able to watch several generated layouts cycle live): `AProceduralScenarioLoader::ClearPreviousScenario`, called at the start of every `LoadProceduralScenario` -- destroys every mesh section component and previously spawned vehicle actor before building the new scenario. Without this, repeated `LoadProceduralScenario` calls against one running session would have accumulated overlapping geometry from every previous scenario instead of replacing it; this was never previously exercised because earlier verification only ever loaded one scenario per session.

All fixes verified against a real live standalone UE5 session (rebuilt, `-game -d3d11`): scenario reload cleanly replaced the previous one across 6 consecutive layouts with 0 skipped meshes/assets each time, before these three bugs were found; the vehicle-position and road-geometry fixes were verified via engine log + regenerated scenario data (see above).

**Update: the vehicle-position fix above was real and necessary but not sufficient** -- the user reported still not seeing vehicles after it shipped. See the next entry for the full, now-conclusive investigation (required building real screenshot-based debugging tools, since diagnostic logs alone had been actively misleading: they reported correct positions and valid, non-degenerate mesh bounds for a genuinely broken render).

Full suite (468 tests, up from 458) and lint clean.

### [RESOLVED] Vehicles still invisible after the position fix -- two more real bugs found via actual screenshots, not logs
Diagnostic logging (added first: real per-vehicle position/rotation/mesh-bounds/visibility logged at spawn time) showed everything looked correct -- `actual_pos` exactly matched `requested_pos`, mesh bounds were non-degenerate and real-vehicle-scale (e.g. a truck at 270x121x75cm half-extents), `hidden=0`, `visible=1`. Logs alone could not explain why vehicles still weren't visible, so real visual ground truth was needed. Built two new permanent RPC debugging methods (`TakeScreenshot`, `DebugMoveCameraTo` -- see `SyntheticDataGenRpcSubsystem.cpp`) specifically to get it, since neither existed before.

1. **The camera was never pointed at the generated content -- confirmed by the first real screenshot.** It showed the current level's own default `/Engine/Maps/Templates/OpenWorld` template geometry (a checkered floor and default mountains), nowhere near the generated scenario's coordinates. The level's default `PlayerStart` has no relationship at all to a generated scenario's own bounds. **Fixed**: `AProceduralScenarioLoader::LoadProceduralScenario` now accumulates the real min/max XY bounds across every parsed mesh vertex *and* every parsed asset position, and repositions the local player's pawn (`RepositionOverviewCamera`, mirroring `default_overview_camera()`'s own positioning logic in `dataset_generator.py`) to overlook that real extent after loading. Confirmed via a follow-up screenshot: real roads and buildings became visible for the first time.

2. **Even with the camera fixed, vehicles still didn't show up in the overview -- because they render as only a tiny fraction of their real geometry.** Using `DebugMoveCameraTo` to zoom in on one specific vehicle's exact logged position (a bus, chosen for size), a close screenshot revealed a tiny dark sliver, not a bus. Root cause, confirmed by directly testing alternate mesh variants at the same position: every vehicle's `SKM_<name>` combined skeletal mesh (the one Phase 1 originally chose) is rigged for City Sample's own runtime damage-state system (Sandbox/Destruction/Deformable variants share one skeleton); without an `AnimBlueprint` actively posing it, the reference pose alone does not show the intact body -- confirmed genuinely broken via screenshot, not assumed. Tested two alternatives directly: `SKM_Exterior_<name>` (a skeletal variant some vehicles have) rendered a full, correct car body when tested on `vehCar_vehicle02`, but is missing for 5 of the 14 vehicles (bus, both non-Exterior trucks, the trailer, one van); `SM_Frame_<name>` (a plain **static** mesh body shell, confirmed present for all 14 vehicles) also rendered correctly when tested on the bus, and has no skeleton/pose dependency at all. **Fixed**: `UVehicleActorSpawner` rewritten to load `UStaticMesh`/`UStaticMeshComponent` instead of `USkeletalMesh`/`USkeletalMeshComponent`; `city_sample_assets.py`'s `VEHICLE_ASSET_PATHS` repointed at every vehicle's `SM_Frame_<name>` path. Real, known, documented limitation: this is the body shell only (no wheels/doors/interior -- those are separate `SM_Wheel_*`/`SM_Door_*` meshes), a real but smaller visual-fidelity gap than "invisible," not attempted to close further in this pass.

**Final confirmation**: a full-scenario overview screenshot after both fixes shows multiple real, recognizable car-shaped silhouettes correctly positioned along the generated roads -- the first time this project has visually confirmed vehicles rendering at all, not just "spawned" per the engine log.

Lesson for this project going forward, recorded because it was expensive to relearn: **a green engine log (spawn succeeded, valid bounds, visible=1) is not evidence of a correct render.** Two of these three root causes (camera pointed at the wrong content entirely, and a skeletal mesh silently rendering almost nothing) produced zero errors or warnings anywhere -- only an actual screenshot revealed either one. `TakeScreenshot`/`DebugMoveCameraTo` are kept as permanent tools for exactly this reason, not deleted after this investigation.

Full suite unaffected by this entry (C++-only change; `city_sample_assets.py`'s catalog test coverage in `test_city_sample_assets.py` already covers path shape/uniqueness generically, no test needed updating for the path values changing).

### [RESOLVED] City Sample asset integration Phase 0: real scenario serializer built; both asset-type investigations resolved with real evidence
Starts a new, planned multi-phase effort (see `feature/city-sample-asset-integration` branch) to replace today's flat-gray procedural boxes with real City Sample assets (vehicles, materials, props, occasional landmark buildings) while keeping this project's own procedural placement/ground-truth logic entirely unchanged — see that branch's plan for the full phase breakdown and the research behind the decision (City Sample's own building-repetition risk, sim2real domain-gap research, five candidate PCG techniques evaluated and mostly rejected as out of scope).

**Found and fixed a real, previously-unknown gap**: no committed code converted a `ScenarioResult` into the JSON shape `UE5Backend.load_scenario`/`ProceduralScenarioLoader.cpp` actually expect. Every real UE5 verification earlier this session (the 696/798/840-mesh scenarios confirmed rendering correctly in a live PIE session) ran through an ad hoc, uncommitted scratchpad script, not through anything the test suite covers or later phases could reuse. Fixed: `src/orchestration/scenario_serializer.py` (`serialize_scenario`), with real round-trip tests (`tests/unit/test_scenario_serializer.py`) verifying vertex/triangle/UV/material data survives the numpy-to-JSON conversion exactly, and that `json.dumps` never raises (a real likely bug class, since every dataclass here holds numpy arrays, which aren't natively JSON-serializable).

Also added `bin/send_scenario_to_ue5.py` -- a real, permanent, tested CLI (generate → serialize → send to a live UE5 editor), replacing the throwaway scratchpad script, matching this project's established `bin/*.py` philosophy (`generate_dataset.py`'s own docstring: only wrap capabilities that genuinely exist). Tested against a real local mock WebSocket server (same pattern as `test_backend.py`) covering the success path, RPC-error path, and timeout path (with a clean, actionable stderr message -- "Is a UE5 editor running with Play-In-Editor started?" -- rather than a raw traceback or silent hang).

**Investigation findings, both resolved with real file-level evidence** (no guessing, no editor needed for either):
1. **Vehicle asset type**: confirmed via direct inspection of `CitySample`'s installed content -- vehicles are real Blueprint actors (`BP_vehCar_vehicle02.uasset`), not plain static meshes. Skeletal mesh + Animation Blueprint (`ABP_vehCar_vehicle02.uasset`) confirm real skeletal rigging (wheel articulation), and a shared base-class hierarchy (`BP_VehicleBase_Drivable`, `_Destruction`, `_Deformable`, `_Sandbox`) confirms real Chaos vehicle physics and damage/deformation systems are involved, not just a mesh. This confirms the real risk already anticipated in the integration plan: Phase 1's C++ spawn path needs `LoadClass<AActor>` + `SpawnActor`, not a simple static-mesh load, and freezing physics immediately after spawn (already planned) is a real necessity, not a precaution -- an unfrozen Chaos-physics vehicle would not stay in its procedurally-computed pose. The `_Sandbox` variant is a real candidate for Phase 1's actual spawn class, since it likely sidesteps the destruction/deformation systems' complexity for a use case that only needs a vehicle to sit still in a frozen scene.
2. **Pedestrian availability outside Mass AI**: strong positive evidence, not yet 100% confirmed. `Content/Crowd/Blueprints/BP_CrowdCharacter.uasset` is a real, standalone Blueprint character class (not fused into Mass Entity data) with substantial variety already modeled -- 6 male + 6 female base characters, each with weight variants (Normal/Over/Under), plus real accessories (backpacks, briefcases, purses, phones). This strongly suggests pedestrians can be spawned the same way vehicles are (Phase 6 need not be deferred/boxes-forever), but whether its animation/pose depends on Mass-AI-injected runtime state can't be fully confirmed from file/folder structure alone -- final confirmation needs an actual standalone spawn attempt in the editor, planned as part of Phase 1's manual PIE verification pass (spawning one `BP_CrowdCharacter` alongside the vehicle work, to close this out in the same session rather than a separate investigation).

Full suite (451 tests, up from 441) and lint clean.

### [RESOLVED] City Sample asset integration Phase 1 (Python side): vehicles sample real City Sample asset paths, no longer build box meshes
Follow-up to the Phase 0 entry above. Vehicles are the highest-priority
category in the integration plan (confirmed-compatible, ~13 real
models, most visually impactful fix) and the first to actually swap
away from procedural box geometry.

`src/procedural/city_sample_assets.py` (new) catalogs real
`VEHICLE_ASSET_PATHS`, keyed by the same vehicle-type strings
`ActorPlacementGenerator` already samples from `vehicle_mix`
(sedan/suv/truck/bus) -- confirmed real (not guessed) via direct
inspection of City Sample's installed content: every non-hero vehicle
folder has a `BP_veh*_Sandbox.uasset` Blueprint. The sedan/suv split is
a documented, deliberately-flagged-as-unverified assignment (City
Sample's folder names don't distinguish body types); flagged for
revisit during this phase's manual PIE verification pass.

`Vehicle` (`actor_placement.py`) gained an `asset_path: str` field,
sampled deterministically alongside `vehicle_type` via the actor's
existing seeded RNG. `dataset_generator.py`'s `generate_scenario` no
longer builds a box mesh per vehicle (`MeshFactory.build_vehicle_mesh`
still exists, used by its own tests and as a documented fallback shape,
just no longer feeds `ScenarioResult.meshes`); ground truth is
unaffected, since `extract_bboxes_3d_vehicles` derives boxes from
`Vehicle`'s own placement-time fields, not from mesh geometry --
confirmed via reading `validator.py`'s `_validate_meshes` (no
cross-check against vehicle count) and grepping the test suite for any
exact-mesh-count assertion that would have broken.

`scenario_serializer.py`'s `"assets"` array (present but empty since
Phase 0) is now populated with one entry per vehicle:
`{"category": "vehicle", "asset_path", "position", "rotation_rad",
"id"}` -- the schema decided in the integration plan.

**C++ side, real end-to-end verification against a live standalone UE5
session (2026-09-16), including two real bugs found and fixed along the
way**:

1. The user manually migrated the 14 chosen `veh*_Sandbox` Blueprints
   (via Epic's Migrate tool) from `CitySample` into `VantageCV_UE5`'s
   Content (2,850 files copied -- the full dependency closure).
2. First real spawn attempt: `LoadClass<AActor>(nullptr, *AssetPath)`
   failed for all 14 vehicles ("spawned 0 asset(s), skipped 50").
   **Real bug, fixed**: `LoadClass` needs the full object path to a
   Blueprint's generated class (`"<package path>.<asset name>_C"`), not
   the bare package path -- fixed in `VehicleActorSpawner.cpp` by
   building that path explicitly.
3. Second attempt still failed, and the engine log revealed the real,
   deeper blocker: every `BP_veh*_Sandbox`'s parent chain ultimately
   depends on `ACitySampleVehicleBase` -- a native C++ class defined in
   **CitySample's own game-project source**
   (`Source/CitySample/Vehicles/CitySampleVehicleBase.h`), not portable
   content. Reading that file confirmed it's deeply wired into
   CitySample's own gameplay framework: Mass AI traffic control
   (`IMassTrafficVehicleControlInterface`), Enhanced Input, a custom
   UI/menu system, photo mode, `ACitySampleCharacter` -- porting it
   would mean dragging in a large, open-ended slice of a game framework
   this project has no use for (scenarios are frozen-frame captures,
   not driveable).
4. **Architectural decision (user-approved after being presented with
   three options: build a minimal custom actor, port
   `ACitySampleVehicleBase` and its dependency chain, or fall back to
   box meshes)**: `UVehicleActorSpawner` was rewritten to spawn a plain
   `AActor` holding just the vehicle's real combined skeletal mesh
   (`SKM_<vehicle folder>`, e.g.
   `/Game/Vehicle/vehCar_vehicle02/Mesh/SKM_vehCar_vehicle02`) via a
   `USkeletalMeshComponent` -- no vehicle movement component, no
   Blueprint class, no gameplay dependencies at all. This is genuinely
   portable content (confirmed via direct inspection of every migrated
   vehicle's `Mesh/` subfolder) and is everything a frozen-pose
   synthetic scene actually needs.
   `src/procedural/city_sample_assets.py`'s `VEHICLE_ASSET_PATHS` was
   updated to point at these skeletal mesh paths instead of the
   `_Sandbox` Blueprint paths.
5. **Real, live confirmation**: rebuilt (`Build.bat`, 0 failed),
   relaunched standalone (`-game -d3d11`, which also starts the RPC
   subsystem -- same `GameInstanceSubsystem` mechanism PIE uses), sent
   a real 112-mesh `urban_dense` scenario over the WebSocket bridge.
   Engine log confirmed: `LoadProceduralScenario: built 112 mesh
   section(s), skipped 0` and `LoadProceduralScenario: spawned 50
   asset(s), skipped 0` -- all 50 placed vehicles spawned successfully,
   no errors/warnings in the load window. (No screenshot/visual capture
   was taken -- there's no RPC method for that yet; log-based
   confirmation of spawn success/positions was judged sufficient for
   this phase, not worth building new screenshot infrastructure for.)

`ProceduralScenarioLoader.cpp` gained `ParseAssetData` (parses one
`"assets"` entry, converting `position` via the existing
`ApplyCoordinateConvention` and negating `rotation_rad`'s sign for the
same mirror-transform reason Y is negated) and a dispatch loop that
spawns one vehicle per `category: "vehicle"` entry; `"prop"`/
`"hero_building"` entries are skipped (not fatal) until later phases
add them.

**Still open, tracked for this phase's completion**: the bbox-precision
spot-check (do the real skeletal mesh silhouettes diverge meaningfully
from the placement-time box across the 14 models?) that decides whether
Phase 7 needs pulling forward -- not yet done, since it needs either a
real screenshot/viewport comparison or an in-editor visual check.

Full suite (458 tests, up from 451) and lint clean.

### [RESOLVED] Road network rearchitected to a plain orthogonal grid -- eliminates the remaining lane-overlap z-fighting entirely
Follow-up to the "[RESOLVED] Two real geometry-overlap bugs" entry
below: that entry's lane-trim fix reduced overlap by 72%/43% but
explicitly couldn't reach zero, because a uniform per-node trim can't
fully clear intersections where two edges meet at a sharp/near-parallel
angle -- and the road network at the time (perturbed-grid + Delaunay
triangulation) could and did produce arbitrary-angle intersections,
including acute ones.

Root-caused via a deliberate design decision, not a further patch:
`src/procedural/road_network.py` was rearchitected from
perturbed-grid + Delaunay triangulation to a plain orthogonal grid --
every node connects only to its immediate +x/-x/+y/-y grid neighbor, so
every intersection is a clean 90-degree crossing. This makes the
existing per-node lane trim (`LaneTopologyGenerator._compute_node_clearance`)
mathematically exact instead of a partial mitigation: perpendicular
roads trimmed back by their own half-width geometrically cannot
overlap. **Verified on the same real scenario shape used throughout
this investigation: 0 overlapping lane-mesh pairs (down from 3,538
originally, 963 after the trim-only fix)** -- confirmed via real mesh
geometry (Shapely), not reasoning about the algorithm. New regression
test: `test_no_lane_overlaps_at_intersections`.

**Real cost, not free**: this removes organic/arbitrary-angle street
variety -- a real, explicit tradeoff, not an oversight (see
road_network.py's own module docstring for the full reasoning).
Diagonal roads may be added back later as an explicit, additional
connection strategy layered on top of the grid, not a revival of the
old point-cloud/Delaunay approach.

**Real downstream consequences, both handled, not just noted**:
1. `building_placement.py`'s `_identify_blocks` used to re-triangulate
   node positions internally (its own separate Delaunay call) and keep
   only triangles whose 3 edges all survived length-filtering. With no
   diagonal edges left in the road graph at all, every such triangle
   failed that check -- **zero blocks, zero buildings placed**, a real
   break caught immediately by the existing test suite (5 tests failed
   with "assert []"), not silently shipped. Fixed by replacing
   triangle-based block *approximation* with exact rectangular
   grid-cell identification (reconstructing rows/columns purely from
   node positions, since this module only receives the generic
   `nodes`/`edges` dicts, not `RoadNetworkGenerator`'s internal grid
   array) -- genuinely more correct, not just a workaround, since real
   city blocks in a grid city are rectangles, not triangle
   approximations.
2. Several `road_network.py`/`test_road_network.py` tests were tied
   directly to the removed Delaunay/perturbation machinery
   (`_find_or_create_node`'s merge-by-distance behavior,
   `QhullError`-wrapping for collinear points) and were removed, not
   just left failing -- that functionality no longer exists, so testing
   it would be testing dead code.

Full test suite (441 tests) and lint clean after all of the above.

### [RESOLVED] Three real UE5 rendering bugs found by actually looking at a rendered scenario (scale, handedness, missing normals)
Found immediately after the first successful end-to-end mesh-dispatch
test (see the "[RESOLVED] LoadProceduralScenario now dispatches real
mesh sections" entry) -- the geometry built, but looked wrong in three
distinct, real ways, each found by actually looking at the viewport,
not by reading code:

1. **1/100th scale.** `src/procedural/mesh_factory.py` generates
   geometry in meters, but Unreal's native unit is centimeters (1
   Unreal unit = 1cm) -- nothing anywhere in the pipeline converted
   between them before this session, so a "20-meter" building rendered
   20 Unreal units tall. Fixed in
   `ProceduralScenarioLoader.cpp::ParseVector3Array` with a
   `MetersToUnrealUnits = 100.0` multiplier at the JSON-ingestion
   boundary.
2. **Buildings missing one or more walls.** `mesh_factory.py`'s own
   module docstring already documented this exact, anticipated gap:
   its geometry is right-handed (CCW front-face winding) but UE5 is
   left-handed (CW front-face winding as seen from outside) --
   "reconciling the two is Phase 4's job (the coordinate transform
   happens at the JSON-RPC boundary when loading into UE5, not here)."
   That boundary just didn't exist until this session. Fixed by
   negating the Y axis for every vertex (`ApplyCoordinateConvention` in
   `ProceduralScenarioLoader.cpp`) -- a mirror transform flips
   handedness and reverses every triangle's perceived winding in one
   step, so no separate triangle-index swap was needed.
3. **Noisy/broken lighting on large flat surfaces (roads).**
   `ScenarioMeshBuilder::BuildMeshSection` called
   `UProceduralMeshComponent::CreateMeshSection` with empty
   normals/tangents arrays (documented at the time as "not yet visually
   verified"). Real visual result: staticky, broken-looking lighting,
   especially visible on roads. Fixed by computing real normals/
   tangents via `UKismetProceduralMeshLibrary::CalculateTangentsForMesh`
   before building the section, the engine's own standard utility for
   this exact situation.

All three verified visually against the same real 840-mesh scenario
used throughout this session's UE5 dogfooding.

### [RESOLVED] Two real geometry-overlap bugs found via actually rendering a scenario in UE5, not any prior unit test
Both bugs existed since Phase 1-2 and were invisible to every prior test
in this codebase -- every existing overlap/setback test checked
buildings against road *centerlines* or fixed distances, never against
the real, rendered lane-mesh geometry. They were only found by
literally looking at a rendered scenario in a live UE5 editor tonight
(see the UE5 integration entries elsewhere in this file) and asking
"why does the road look staticky and why do buildings clip through it."

**Bug 1: lane geometry overlapped itself at every intersection.**
`lane_topology.py`'s `_generate_lanes_for_edge` offset each edge's full,
untrimmed centerline into lanes -- every edge meeting at a shared node
extended its lane boundaries the entire way to that exact point, with
no clipping. Quantified on a real generated `urban_dense` scenario (128
edges, 25 nodes): **3,538 overlapping lane-mesh pairs, totaling 96,319
sq m of overlap out of the scenario's 250,000 sq m total area (~38% of
all ground area)**. This is what rendered as a "staticky"/noisy-looking
road surface in UE5 -- real z-fighting between overlapping coplanar
meshes, not a rendering bug.
**Fix**: `LaneTopologyGenerator._compute_node_clearance` computes, per
node, the widest connecting road's own lane half-width
(`num_lanes * LANE_WIDTH_METERS`, max over every edge touching that
node); `_generate_lanes_for_edge` now trims each edge's effective
centerline short of both endpoint nodes by that amount (capped at 40%
of the edge's own length, so a short edge can't be trimmed to zero/
negative length) before offsetting lanes from it. Reduced overlap to
963 pairs / 55,019 sq m (a 72%/43% reduction) -- **not fully
eliminated**: a uniform per-node trim can't fully clear intersections
where two edges meet at a sharp/near-parallel angle, since their lane
strips still run alongside each other for a stretch beyond the trim
point. A real fix for that needs an angle-aware miter/wedge computation
per intersection, real additional scope not attempted here. There is
also now a visible unpaved gap at every intersection (no actual
junction/intersection surface mesh is generated to fill it) -- a
known, accepted simplification, not an oversight.

**Bug 2: buildings could stand inside a multi-lane road's actual pavement.**
`building_placement.py`'s `_too_close_to_road` enforced only
`config.road_setback_meters` (a small fixed margin -- 2.0m/4.0m for
this project's templates) from the road *centerline*, but a road's real
physical half-width from centerline is `edge.num_lanes *
LANE_WIDTH_METERS` (up to 14m for a 4-lane edge) -- the fixed setback
never accounted for that. Quantified on the same real scenario: **194
of 283 buildings (~69%) overlapped real lane-mesh geometry, totaling
11,615 sq m**. This is what rendered as buildings visibly clipping
through the road surface in UE5.
**Fix**: the setback enforced against each road segment is now
`config.road_setback_meters + edge.num_lanes * LANE_WIDTH_METERS`
(computed per-edge, since different edges can have different
`num_lanes`), not a single global value. Verified **fully resolved** on
the same scenario: 0 buildings overlap real lane geometry after the
fix (down from 194). Building count per scenario drops accordingly
(283 -> 83 on this seed) since the wider effective setback leaves less
usable space per block -- an expected, honest tradeoff of placing
buildings a realistic distance from actual road pavement, not a
regression.

Both fixes verified against real, rendered geometry (via Shapely,
unioning actual mesh triangles -- not a reimplementation of the same
formula the bugs were in) in new regression tests:
`test_lanes_are_trimmed_short_of_intersections`,
`test_no_building_overlaps_actual_lane_pavement`. Full test suite (442
tests) and lint remain clean.

### [DEFERRED] No actual RGB image files are ever produced -- COCO `file_name` references a file that doesn't exist on disk
Found via a real dogfooding pass (generating a genuine dataset with
`bin/generate_dataset.py` and inspecting the output, not just reading
code): `annotations.json`'s `images[].file_name` field (e.g.
`"proc_scenario_0000.png"`) never corresponds to an actual file anywhere
in `output_dir` -- only `annotations.json` and per-scenario
`*_metadata.json` files are written. This is not a bug (there is no
rendering engine anywhere in this pipeline to produce an actual image
from -- a real UE5.4 install now exists and the plugin compiles/loads
(see the resolved UE5 entries elsewhere in this file), but nothing in
`generate_dataset`'s own call path invokes `UE5Backend`/UE5 at all, and
the UE5-side WebSocket JSON-RPC server needed to receive a real render
request doesn't exist yet either), but it was not previously stated
anywhere a user would see it before hitting it themselves. A caller
expecting a real image-plus-annotations COCO dataset (e.g. to train a
model, or to visually spot-check output) needs to know this up front,
not discover it by a missing-file surprise.
**Action**: documented explicitly in `docs/user_guide.rst`'s CLI section
and this entry; revisit once the UE5-side WebSocket bridge exists and
`generate_dataset` actually calls it to render a frame.

### [RESOLVED] `default_overview_camera` framed scenarios poorly, leaving most of the image empty
Found via the same dogfooding pass as the entry above: since no
rendering engine exists to eyeball an actual rendered frame against, a
top-down 2D plot of a real generated scenario was compared side-by-side
against `default_overview_camera`'s own projected 2D annotation boxes
for that same scenario. The projected content filled only ~55% of the
image's width and left large empty margins on most sides -- a real,
visually obvious framing problem that no existing test caught (every
existing test only checked that *some* boxes projected successfully,
never how much of the frame they used).

Root cause: the camera's offset (`extent * 0.3`) and height
(`extent * 0.6`) ratios positioned it too far back and too high above
the scenario, at too shallow a viewing angle, for its 90-degree
horizontal FOV to fill the frame with actual scene content. Resolved by
retuning both ratios (`0.3` → `0.05`, `0.6` → `0.35`), found by
iterating side-by-side against the same visual comparison until content
filled a healthy majority of the frame, verified to lose no meaningful
number of visible annotations (506 → 489 boxes visible, ~3%, from
perspective changes at the new vantage, not clipping). A regression test
(`test_default_overview_camera_fills_a_reasonable_fraction_of_the_frame`)
now asserts the union of projected 2D boxes spans a healthy majority of
the image in both axes, so this can't silently regress again.

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

### [RESOLVED] No CLI entry points (`bin/generate_dataset.py` etc.)
Was: every capability this pipeline has was only reachable by importing
the Python API directly, not via a command-line tool.

Resolved by `bin/generate_dataset.py`: an argparse wrapper around
`src.orchestration.dataset_generator.generate_dataset`, using the
`config_loader.py` entry above for its `--config` flag. Handles the two
sys.path gotchas real `bin/` scripts hit in a `src`-layout project: it
inserts the repo root onto `sys.path` before importing `src.*` (running a
script directly puts the script's own directory on `sys.path`, not the
repo root or cwd), and it catches `FileNotFoundError`/`NotImplementedError`/
`ValueError` around config loading and generation to print a clean
one-line message on stderr and exit 1, rather than a raw traceback for
every-day failure modes (bad config path, unsupported scenario type,
`ScenarioValidator` failure). `scripts/run_linter.sh` and
`lint_and_test.yml` both extended to run pylint/mypy against `bin/` too,
not just black/isort as before -- it's real code now.

The other four `bin/*.py` scripts MASTER_PROMPT's Phase 0 file tree lists
(`validate_dataset.py`, `profile_performance.py`, `visualize_scenarios.py`,
`compare_sim2real.py`) still don't exist -- none of them wrap an existing
standalone capability this codebase has (there's no sim2real comparison
logic to expose a CLI for, for instance; see the Sim2real entry above).
Building them now would mean inventing functionality, not exposing
something real, so they're left deferred rather than stubbed out.

A dedicated `documentation.yml` CI workflow (also in MASTER_PROMPT's file
tree) was deliberately not built: `tests/integration/test_docs_build.py`
already runs both the HTML and doctest Sphinx builds as part of the
existing `lint_and_test.yml` `test` job, so a separate workflow would
duplicate that coverage without adding any -- the only thing it could add
(publishing built HTML docs somewhere, e.g. GitHub Pages) wasn't asked
for and needs a deliberate hosting decision, not just a workflow file.

`config_loader.py`'s `import yaml` needed a `mypy --strict` override
(`pyproject.toml`'s `[[tool.mypy.overrides]] module = "yaml.*"`, same
pattern as the pre-existing scipy override): `pyyaml` 6.0.1 ships no
`py.typed` marker, and a real `types-PyYAML` stub package exists but
adding it as a dependency would need regenerating `poetry.lock` via
`poetry lock`, which isn't possible in every environment this project is
built in (see the "Poetry install/lint/test flow" entry below). Revisit
if/when a real Poetry install is confirmed available.

### [DEFERRED] No real multi-node/multi-GPU scaling test; CPU-core parallelism confirmed sub-linear, root cause still open
MASTER_PROMPT Section 3.8 lists "Scaling tests (2GPU, 4GPU, 8GPU)" and
"Scaling efficiency" as a test bullet. Neither is implemented: this
environment has no GPUs and no multi-node cluster, and (more
fundamentally) this pipeline's actual workload is pure CPU/NumPy
geometry generation -- nothing in Phases 1-6 touches a GPU, so GPU-count
scaling isn't a meaningful axis for this codebase regardless of
environment.

What's implemented instead is genuine CPU-core parallelism via Ray's
local scheduler (`distributed_runner.py`). This entry's own earlier
"Action" (benchmark actual wall-clock scaling before assuming Ray
parallelism is paying off) has now been done, via real dogfooding on a
32-core machine (`generate_dataset` vs. `generate_dataset_distributed`,
same seed/config, output diffed to confirm byte-identical -- confirmed,
`images`/`annotations`/`categories` all exactly equal): 4 workers gave
1.29x speedup at 12 scenarios and 1.82x at 40; 8 workers gave 2.14x at
40. Real parallelism is genuinely happening (speedup improves with more
scenarios and more workers, and this is nowhere near CPU-starved on 32
cores), but it's well short of the 4x/8x linear ceiling the worker count
alone would suggest -- confirming the risk this entry already predicted
("per-task overhead... could dominate for cheap scenarios") with real
measurements, not just a hypothesis.
**Action**: the specific bottleneck (Ray's own per-task scheduling/IPC
overhead vs. serialization cost of each scenario's `CocoFrame` return
value vs. something else) hasn't been isolated -- would need per-task
profiling (e.g. Ray's own timeline view) to pin down before attempting
to fix. Revisit if real distributed generation at dataset scale
(thousands of scenarios, where the fixed overhead matters proportionally
less) makes this worth optimizing.

### [RESOLVED] Resumable/checkpointed generation verified via a real simulated crash, not just the mocked unit test
`tests/integration/test_resume_handler.py` already covered this
correctness claim, but via a test double, not an actual interrupted
process. Dogfooded for real instead: ran `generate_dataset_resumable`
for a full 8-scenario dataset as a baseline, then in a separate output
directory, called it first for only 4 scenarios (a real, deliberate
stand-in for "the process was killed after 4 scenarios" -- same
`checkpoint.json`/`*_coco_part.json` files a real crash would leave
behind), then called it again for all 8 on that same directory (exactly
what a restarted process pointed at the same `--output-dir` would do).
The "resumed" call took 2.94s versus the "partial" call's 2.87s -- not
the uninterrupted baseline's 5.86s -- confirming it genuinely skipped
regenerating the 4 already-completed scenarios rather than merely
reproducing the same result a second time. Final output
(`images`/`annotations`, including post-merge annotation ID
renumbering) was byte-identical between the uninterrupted and
interrupted-then-resumed runs. No bug found; this closes the loop on
"resumable generation was tested, but only against a mock" as a real,
independently-verified guarantee.

### [RISK] `pkg_resources` (needed by Ray, via the pinned `setuptools<81`) is slated for removal by setuptools upstream
The fix above pins `setuptools<81` specifically to keep `pkg_resources`
importable, because `ray` 2.9.3's `ray/_private/pydantic_compat.py` does
`from pkg_resources import packaging` unconditionally whenever a remote
task is first submitted. `pkg_resources` itself now warns on import:
"slated for removal as early as 2025-11-30." When that happens, this
pin will stop being satisfiable (or satisfiable only with an
increasingly ancient setuptools), and every `ray.remote(...).remote()`
call in this codebase will break again the same way.
**Action**: watch for a `ray` release that no longer imports
`pkg_resources` (newer Ray versions past 2.9.3 likely already fixed
this internally) and upgrade `ray` + drop the `setuptools<81` pin
together, rather than pinning setuptools indefinitely.

### [RISK] Ray adds meaningful test-suite startup overhead
Adding `ray` as a dependency increased the full test suite's wall-clock
time noticeably (roughly 50s to 80s) even though only a handful of tests
actually use it -- `ray.init()`'s worker-process startup cost is paid at
least once per test session. Not a correctness issue, but worth knowing
if test suite speed becomes a concern; consolidating Ray-dependent tests
to share one `ray.init()` call (e.g. via a session-scoped fixture) would
likely help if this grows further.

### [DEFERRED] NuScenes format conversion not implemented
MASTER_PROMPT Section 3.7 lists "NuScenes format conversion" as a Phase 6
bullet. Not implemented. NuScenes' schema (scene, sample, sample_data,
ego_pose, calibrated_sensor, category, instance, sample_annotation
tables, cross-referenced by token) is fundamentally built around
*temporal sequences of ego vehicle poses observing dynamic objects*
(vehicles, pedestrians, cyclists) -- this codebase generates dynamic
objects now (`actor_placement.py`, below) but still no multi-frame
temporal sequences (every scenario is a single independent frame). A
NuScenes export of one frame's static+dynamic objects would be
schema-conformant in the narrowest sense but wouldn't represent what the
format is actually for, and building one now would mean inventing
placeholder ego-motion semantics with nothing real to back them. Revisit
once multi-frame temporal scenario generation exists -- not in
MASTER_PROMPT's roadmap as it stands.

### [DEFERRED] Sim2real distribution analysis not implemented
MASTER_PROMPT Section 3.7 lists "Sim2real distribution analysis" as a
bullet, and Section 1.1's architecture diagram lists a "Sim2Real
Validator (domain gap analysis)." Not implemented: doing this
meaningfully requires a real reference dataset to compare distributions
against (e.g. real building-height distributions, real traffic patterns),
and none exists anywhere in this codebase or its dependencies -- CLAUDE_
SKILLS_AND_PROMPTS.md's own Skill 13 (Sim2Real Validation) prompt template
explicitly expects the user to supply reference data, which nobody has
in this context. `sanity_checker.py`'s `check_building_height_distribution`
is the closest analogue actually implemented: it compares generated
output against the *configured* distribution (not a real-world one),
which is a real, useful check but not sim2real analysis in the sense the
spec means.

### [RESOLVED] COCO export only carried building/"structure" annotations
Was: `coco_exporter.py` declared exactly one category ("building"), since
no vehicle/pedestrian placement existed anywhere in the pipeline.
Resolved by `actor_placement.py` (see the ground-truth entry below):
`coco_exporter.py` now declares every category in
`src.ground_truth.categories` (building, sedan, suv, truck, bus,
pedestrian) and reads each annotation's real `category_id` from its
source `BoundingBox3D` rather than hard-coding `BUILDING_CATEGORY_ID`.
Cyclists are still not a category -- `ScenarioTypeConfig.vehicle_mix` has
no cyclist entry, and nothing in MASTER_PROMPT's roadmap asks for one.

### [RESOLVED] LiDAR ray-casting and depth-map rendering had no spatial acceleration structure
Was: `lidar_model.py`'s `LidarSensor.scan` and `depth_map.py`'s
`render_depth_map` were both O(rays * triangles) / O(pixels * triangles)
brute force -- every ray tested against every triangle of every mesh,
with tests kept deliberately small specifically because of this.

Resolved by `lidar_model.py`'s `TriangleGrid`: a uniform 3D grid built
once per scene (triangles binned into cells sized so each holds roughly
`target_triangles_per_cell` on average), then queried per ray via
Amanatides & Woo's 1987 voxel-traversal algorithm -- a ray only tests
triangles in the cells it actually passes through, walked in distance
order with early termination the moment a found hit is closer than the
next unvisited cell could possibly contain anything. This is an *exact*
acceleration structure, not an approximation: verified directly (200+
randomized scenes/rays plus explicit axis-aligned-ray and
`LidarSensor.scan`-level cases in `test_lidar_model.py`) to return
bit-identical results to the brute-force `closest_hit_distance` on the
same scene. `closest_hit_distance` itself is kept as the simple
reference implementation (and as what `TriangleGrid` is verified
against) but is no longer on either module's hot path -- both
`LidarSensor.scan` and `render_depth_map` build one `TriangleGrid` and
reuse it across every ray of the sweep/image, rather than rebuilding
(or re-scanning every triangle) per ray.

One subtlety worth recording: `LidarSensor.scan` only passes
`max_range_m` as the grid's search cutoff when `range_noise_std_m == 0`.
With noise enabled, a *true* hit just beyond `max_range_m` can still be
reported if noise happens to pull the measured range back within range
(a real noisy sensor could do the same) -- bounding the search to
`max_range_m` in that case would silently make such hits impossible to
find at all, changing behavior rather than just accelerating it.
**Action**: none -- `depth_map.py`'s `render_depth_map` has no analogous
range cutoff to worry about, so it always passes no `max_distance` limit.

### [RESOLVED] `TriangleGrid.closest_hit` silently dropped real hits on flat/coplanar geometry -- found via a genuine cross-platform CI failure
First push of `TriangleGrid` passed every test locally (Windows) but
`test_lidar_hit_points_lie_on_ground_plane` failed on GitHub Actions'
Ubuntu runner: `assert len(points) > 0` got `0`. Per this project's own
standing rule, the real CI log was pulled (pasted by the user, since this
environment's `gh` isn't authenticated and the Actions logs API returns
403 without admin rights) rather than guessed at -- and reproducing the
exact failing scan locally revealed the bug was real and
platform-*independent*, just triggered by different rays on Windows vs
Linux (1 of the scan's 3 elevation rings failed locally too; Linux's
`libm` cos/sin gave slightly different values that pushed more rings over
the same edge).

Root cause: a mesh entirely at one z value (a flat ground/road plane --
extremely common in this codebase) collapses the grid's own z-extent to
a single thin cell, so the geometry sits exactly on that cell's boundary.
`closest_hit` was checking each candidate triangle hit against `t_max`,
a bound computed from the grid's own AABB-slab-intersection formula --
a *different* formula from the Moeller-Trumbore ray-triangle math that
produced the actual hit distance. For a ray grazing that shared
boundary, the two formulas can disagree by a few ULPs, and when the
triangle-intersection result came out numerically *larger* than the
AABB-derived bound, the real hit was rejected by `hit <= t_max` even
though it was the closest (only) geometry there.

Fix: separated two bounds that had been conflated. `traversal_limit`
(from the grid's own AABB math) now only governs when to stop visiting
*new* cells; `accept_limit` (the caller's own `max_distance`, or
unbounded) is what a *found* triangle hit is actually checked against.
A hit discovered while testing a cell the traversal already legitimately
visited is accepted on the caller's own terms, not rejected against the
grid's internal, approximate bookkeeping. Added a regression test
(`test_triangle_grid_finds_hits_grazing_flat_scene_boundary`) pinning
the exact failing scan config, and strengthened
`test_lidar_hit_points_lie_on_ground_plane` from `len(points) > 0` to an
exact expected count, so a partial regression (some but not all rays
affected, as happened here) fails loudly instead of slipping through a
weaker assertion again.

### [RESOLVED] Segmentation mask rasterization was O(width * height) per object
Was: `rasterize_instance_masks` ran one *full-image*
`matplotlib.path.Path.contains_points` pass per object, regardless of
how much screen space the object actually covered -- the same class of
gap as the LiDAR/depth-map entry above, just for a different (non-ray-
casting) algorithm.

Resolved by `_paint_silhouette`: each object's point-in-polygon test now
only runs over its own projected silhouette's pixel bounding box,
clipped to the image, instead of the full frame -- every pixel outside
that box is trivially outside a convex silhouette too, so this is an
*exact* optimization, not an approximation (verified directly against a
brute-force full-image reference across 100 randomized convex polygon
shapes/positions, including ones partially or fully outside the image,
in `test_segmentation.py`). For a small object in a large (e.g.
1920x1080) frame this is a two-to-three-order-of-magnitude reduction in
points tested -- exactly the "real HD-resolution frame" case this entry
originally called out as slow.

### [RESOLVED] Ground truth extraction only covered buildings, not vehicles/pedestrians
Was: `bbox_3d.py`, `bbox_2d.py`, and `segmentation.py` all operated on
`Building` objects only -- no vehicle/pedestrian placement existed
anywhere in the pipeline, and MASTER_PROMPT never specifies one for any
phase (`ScenarioTypeConfig.vehicle_mix` since Phase 1 and
`TrafficNetworkGenerator`'s driving/pedestrian `SpawnZone`s since Phase 3
both sat unused for their obvious purpose until now).

Resolved by adding `src/procedural/actor_placement.py`
(`ActorPlacementGenerator`): places vehicles/pedestrians at
`TrafficNetworkGenerator`'s own spawn zones (one occupancy roll per zone,
sampled from `config.traffic_density`; vehicle type sampled from
`config.vehicle_mix`; heading derived from the spawn zone's own road
edge direction), with AABB-overlap rejection between vehicles.
`BoundingBox3D` gained `heading_rad` (a real rotation applied in
`corners()`, not just axis-aligned) and `category_id`
(`src.ground_truth.categories`, shared with `coco_exporter.py` so the two
can't drift). `MeshFactory` gained `build_vehicle_mesh`/
`build_pedestrian_mesh` (oriented boxes, same topology as
`build_building_mesh`). `dataset_generator.render_frame` combines all
three object kinds' `BoundingBox3D`s with an id-offset scheme (each
kind's own 0-based counter offset by the preceding kinds' counts) so
`object_id` stays globally unique per frame.

Three deliberate scope decisions made along the way, not covered by any
spec (MASTER_PROMPT never specifies vehicle/pedestrian placement at all):
- **Pedestrian occupancy** is `traffic_density`'s own sampled fraction
  times a fixed `PEDESTRIAN_DENSITY_FRACTION_OF_TRAFFIC = 0.3` constant,
  since `ScenarioTypeConfig` has no dedicated pedestrian-density field
  and adding one for a single module felt like the wrong place to extend
  the schema.
- **No bounds-containment check** for vehicles/pedestrians in
  `ScenarioValidator` (only finiteness) -- unlike buildings, which get an
  explicit `ROAD_SETBACK_METERS` margin *guaranteeing* their footprint
  stays inside `bounds`, vehicles/pedestrians are anchored directly at
  spawn zone positions, which are themselves never bounds-checked (see
  `test_traffic_network.py`) and can legitimately sit at/past the road
  network's edge. Adding a strict check here surfaced this immediately
  as real end-to-end generation failures, not a false positive to
  special-case around.
- **Vehicles/pedestrians are represented as boxes still** for meshes (no
  wheels/limbs/detail) and are static (no motion, no lane-following
  behavior) -- placement only, matching this phase's actual scope.
  Per-lane turn connectivity (needed for real vehicle *navigation*, as
  opposed to placement) remains deferred -- see that entry below.

Road/lane ground truth (as opposed to vehicles/pedestrians) is still not
extracted -- nothing in MASTER_PROMPT's Phase 5 bullets asks for it, and
roads/lanes aren't "objects" in the AV-perception sense a COCO category
would represent.

### [RESOLVED] No sensor noise model
Was: camera projection, LiDAR ray-casting, and depth rendering were all
perfectly noise-free; MASTER_PROMPT's own `camera_front.yaml`/
`camera_rear.yaml` config templates (Phase 0) already declared a
`distortion_model`/`distortion_coeffs` field that nothing read.

Resolved: `CameraIntrinsics.distortion_coeffs` (Brown-Conrady k1/k2/p1/
p2/k3, applied in `Camera.project` between normalization and the
intrinsic matrix -- standard OpenCV ordering/formula), `LidarConfig
.range_noise_std_m` (zero-mean Gaussian noise on each ray's measured
range, applied before the `max_range_m` check so noise can legitimately
both create and drop hits near the boundary), and `render_depth_map`'s
`noise_std_m` (same Gaussian treatment, applied only to finite/hit
pixels, clamped to stay positive). All three default to
off/`None`/`0.0` -- every pre-existing caller and test keeps behaving
exactly as before -- and every real sensor profile shipped in this repo
(`configs/sensor_profiles/*.yaml`) uses all-zero distortion coefficients
anyway, so this changes no default output anywhere in the pipeline.

`LidarSensor.__init__` and `render_depth_map` both raise `ValueError` if
their noise std is nonzero but no `seed` is given -- deterministic noise
requires a real seed, the same discipline every other generator in this
codebase already follows; no silent OS-entropy randomness sneaking into
an otherwise fully-reproducible pipeline.

Deliberately still out of scope:
- **Pixel quantization** for cameras: `bbox_2d.py`'s box-width/area math
  currently relies on sub-pixel-precision floats; explicitly rounding
  projected pixels to an integer grid would touch that math for
  uncertain benefit and wasn't asked for. Revisit only if a caller
  actually needs quantization-level realism.
- **Loading distortion coefficients from `configs/sensor_profiles/*.yaml`**
  at runtime: those files are still reference-only, exactly like the
  scenario templates were before `config_loader.py` (see that entry
  above) -- nothing reads them. Would need its own loader analogous to
  `load_scenario_config`, not attempted here since the ask was a noise
  *model*, not a sensor-config *loader*.

### [RISK] `UE5Backend`'s per-call connection setup makes the master prompt's <100ms/<2s latency budgets unverifiable as literally stated
`UE5Backend.call()` opens a brand-new WebSocket connection for every RPC
call (documented as a deliberate simplicity tradeoff in backend.py).
Measured directly and repeatedly against a local mock server: round-trip
time for the *same* call varied from well under 100ms to over 2 seconds
across otherwise-identical runs on this machine, with values landing
suspiciously close to whole seconds (e.g. 2.04s) -- consistent with
intermittent external interference on new local socket connections (most
likely antivirus real-time scanning on Windows), not a bug in the
request/response logic itself (which is 100% covered and passes every
functional test). The tests now assert only generous smoke-test bounds
(<5s) rather than the spec's literal targets.

**Update 2026-09-15, against a real UE5 server (not the mock)**: once
the actual UE5-side WebSocket RPC bridge was built (see the
"[RESOLVED] WebSocket JSON-RPC bridge" entry below), a real `Ping`
round trip via `ws://localhost:8765` landed consistently at ~2.1s
across 4 separate calls -- squarely in the same suspicious ~2-second
range as the mock-server variance above, which strengthens (not
proves) the antivirus/socket-interference theory: this is a second,
independent data point at nearly the same value against a completely
different server implementation. A related, still-unexplained
oddity found in the same session: connecting explicitly to
`ws://127.0.0.1:8765` or `ws://[::1]:8765` (rather than `localhost`)
was refused outright (`ConnectionRefusedError`) on both, even though
`localhost` itself connects successfully -- inconsistent with a simple
"IPv6 attempted first, times out, falls back to IPv4" explanation,
since neither literal loopback address works alone. `Server->Init()`
was called with an empty `BindAddress` (documented as "bind to all
interfaces"); what interface `localhost` actually resolves to and
successfully reaches on this machine, that neither loopback literal
does, was not investigated further.
**Action**: if real <100ms production latency is ever required, switch to
a persistent connection (connect once, reuse for many calls) rather than
per-call connect/disconnect -- this removes handshake cost from the
steady-state latency and would likely resolve the spec's target being
achievable in practice, though it doesn't explain the *variance* seen
here, which needs testing on a machine without the same local antivirus
configuration to confirm the root cause.

### [RESOLVED] LoadProceduralScenario now dispatches real mesh sections -- verified end-to-end, visually, against a real scenario
Was: `AProceduralScenarioLoader::LoadProceduralScenario` only validated
that its input was well-formed JSON; it never dispatched per-mesh
`UScenarioMeshBuilder::BuildMeshSection` calls, so no geometry was ever
actually built from a real payload.

Resolved 2026-09-15/16: implemented real parsing of the `"meshes"`
array (`vertices`/`triangles`/`uvs`/`material`, matching
`src/procedural/mesh_factory.py`'s `Mesh` dataclass field-for-field --
vertices/uvs as `[[x,y,z], ...]`/`[[u,v], ...]` JSON arrays, triangles
as a flat int list), and for each entry: spawn a real
`UProceduralMeshComponent` on the loader actor and call
`UScenarioMeshBuilder::BuildMeshSection` on it. Verified with a real,
full end-to-end test, not a synthetic small payload: generated one
real `urban_dense` scenario via this repo's own
`generate_scenario` (840 meshes), sent it over the real WebSocket
bridge (see the entry above) to a live UE 5.4.4 editor with PIE
running, and confirmed via the editor's own log
(`LogProceduralScenarioLoader: Display: LoadProceduralScenario: built
840 mesh section(s), skipped 0`) that every single mesh built
successfully -- then confirmed **visually**, in the PIE viewport, that
real geometry (roads, buildings) was actually there. This is the first
time any geometry this pipeline generated has ever been seen rendered
by an actual engine, rather than only plotted via matplotlib or
asserted correct by a unit test.

**Still open**: traffic controller initialization (no such actor class
exists yet) and streaming/culling (needs profiling against a real,
populated level) -- MASTER_PROMPT Section 3.5's other two "Procedural
Meshes"/"Traffic Network" bullets for this phase. Also: the JSON
schema used here (`{"meshes": [{"vertices", "triangles", "uvs",
"material"}, ...]}`) only covers meshes -- `nodes`/`edges`/`lanes`/
`buildings`/`traffic` from `ProceduralScenarioLoader.h`'s own original
docstring shape are not sent or parsed; revisit if UE5-side traffic
light/stop-sign visualization or road-lane-level detail ever becomes
a real requirement, rather than just visualizing raw mesh geometry.

### [RESOLVED] UE5 plugin compiled and loaded into a real UE 5.4.4 editor for the first time
Every prior entry in this file about `unreal_plugin/` being "unverified"
or "never compiled" is now stale for the compile/load step specifically
(runtime behavior of `BuildMeshSection`/`LoadProceduralScenario` is
still unverified -- see their own entries). Dogfooded for real: UE
5.4.4 installed, a fresh C++ host project created at
`F:\UE5Projects\VantageCV_UE5\`, `unreal_plugin/SyntheticDataGen/`
copied into its `Plugins/` folder, and compiled via a real Visual
Studio 2022 build -- not guessed at from documentation.

Found and fixed two real bugs the "never compiled" code had accumulated:
1. `ScenarioMeshBuilder.cpp`'s `BuildMeshSection` declared its empty
   vertex-colors array as `TArray<FLinearColor>`, but
   `UProceduralMeshComponent::CreateMeshSection`'s real signature takes
   `const TArray<FColor>&` (a different overload,
   `CreateMeshSection_LinearColor`, takes `FLinearColor` instead) --
   real compile error (`C2665: no overloaded function could convert all
   the argument types`), not a guess. Fixed by changing the array's
   element type to `FColor`.
2. `SyntheticDataGen.uplugin` used the built-in `ProceduralMeshComponent`
   plugin's module without declaring it as a plugin dependency in the
   `"Plugins"` array -- UnrealBuildTool warned about this rather than
   erroring, but it's the kind of thing that can silently break in a
   packaged build; fixed by adding the dependency entry.

Also required real environment fixes unrelated to this codebase's own
C++ (Visual Studio 2026 was too new for UE5.4's toolchain detection and
had to be uninstalled in favor of VS2022; UE5.4 additionally rejects
VS2022's own default MSVC v143 14.44 toolset with a real compile error
in Engine/Core headers, fixed by installing the older v14.38 toolset
and pinning `UnrealBuildTool`'s `BuildConfiguration.xml` to use it) --
none of that is specific to this project, so not detailed further here.

**Still open, separately**: the editor crashes on normal launch
(`EXCEPTION_ACCESS_VIOLATION` in the D3D12 shader compiler,
`UnrealEditor-ShaderPreprocessor.dll`) on this particular machine,
correlated with a very new (2026-era) NVIDIA driver and Windows 11
build against a mid-2024 engine. Workaround: launch with the `-d3d11`
flag. Not yet root-caused or fixed for real; see whoever picks this
back up for the exact driver/build versions involved before assuming
it's resolved.

### [RESOLVED] WebSocket JSON-RPC bridge built and a real Ping round trip confirmed against a live UE5 editor
The piece that made `src/ue5/backend.py` untestable against anything
real: nothing on the UE5 side ever hosted a WebSocket JSON-RPC server
to receive `UE5Backend`'s `Ping`/`LoadProceduralScenario` calls, so
every test of that module was against a local Python mock, never a
real engine. Built `USyntheticDataGenRpcSubsystem`
(`unreal_plugin/.../Networking/SyntheticDataGenRpcSubsystem.{h,cpp}`),
a `UGameInstanceSubsystem` that hosts a server via the engine's own
`WebSocketNetworking` plugin (`Engine/Plugins/Experimental/
WebSocketNetworking`) and answers `Ping` and `LoadProceduralScenario`
(dispatching to `AProceduralScenarioLoader`, spawning one into the
current world if none exists). Starts listening automatically once a
GameInstance exists (i.e. on Play-In-Editor start, not merely from the
editor being open) on port 8765, matching `backend.py`'s own docstring
example URI.

Real, non-mocked verification: `UE5Backend("ws://localhost:8765").ping()`
run from this repo's own Python against the live PIE session returned
successfully, repeatedly (~2.1s each across 4 calls -- see the
`[RISK]` latency entry above for what that number means and doesn't).

Getting a clean compile took three real, wrong-then-fixed attempts
worth recording since they're non-obvious and would trip up anyone
else adding a `TUniquePtr<ForwardDeclaredType>` member to a `UCLASS`:
1. First attempt: `TUniquePtr<IWebSocketServer> Server` member, no
   custom constructor/destructor. Real error: `C4150: deletion of
   pointer to incomplete type`, because the class's implicit
   destructor (generated inline in the header, where
   `IWebSocketServer` is only forward-declared) needs the complete
   type.
2. Second attempt: declared the constructor and destructor
   out-of-line (defined in the .cpp, where the full type is included)
   -- standard C++ Pimpl practice. Still failed with the *same* error,
   now traced (via the compiler's own template-instantiation-context
   notes) to a *different*, UHT-generated constructor:
   `DEFINE_VTABLE_PTR_HELPER_CTOR`, a hot-reload-support constructor
   UnrealHeaderTool auto-emits into every `UCLASS`'s `.gen.cpp`,
   independently of any constructor the class itself declares.
3. Third attempt: tried declaring `DECLARE_VTABLE_PTR_HELPER_CTOR`
   manually to suppress UHT's auto-generation and supply our own
   out-of-line definition -- turned out `GENERATED_BODY()` *already*
   declares this constructor unconditionally (confirmed by reading the
   actual generated `.generated.h`), so this was a duplicate
   declaration (`C2535`), not a fix.
4. **What actually worked**: switched `Server` from `TUniquePtr<IWebSocketServer>`
   to a plain `IWebSocketServer*`, with manual `delete` in
   `Deinitialize()`. A raw pointer has no destructor/constructor of
   its own to instantiate, so none of the above machinery (implicit
   destructors, UHT's `FVTableHelper` ctor) ever needs the complete
   type at all -- sidesteps the entire category of problem rather than
   fighting it. `TPimplPtr` (Epic's own purpose-built Pimpl smart
   pointer) was considered and rejected: it requires constructing the
   pointee via its own `MakePimpl` factory, but `IWebSocketServer`
   instances come from `IWebSocketNetworkingModule::CreateServer()`
   instead, which `TPimplPtr` can't take ownership of.

**Still open**: `LoadProceduralScenario`'s own dispatch through this
bridge (not just `Ping`) hasn't been tested against a real scenario
payload yet -- see the "[DEFERRED] LoadProceduralScenario" entry above,
which is itself still a stub past JSON validation.

### [DEFERRED] Master prompt Section 3.4 (Phase 3) contradicts Section 1.1 on which language owns mesh generation
MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md Section 3.4 labels
"Procedural Meshes" as "(C++ in UE5)". Section 1.1's own architecture
diagram, by contrast, lists a "Procedural Mesh Factory (Geometry)" as
part of the Python-side "PROCEDURAL GENERATION ENGINE" box, distinct from
UE5's "Procedural Mesh Component (Real-time Generation)" in the C++
simulation backend. These directly conflict. Resolved in favor of the
testable interpretation: `src/procedural/mesh_factory.py` computes
vertex/triangle/UV buffers in Python; a C++ `UScenarioMeshBuilder` class
exists under `unreal_plugin/.../ProceduralMesh/` as the UE5-side
consumer of that data -- now confirmed to actually compile and load
(see the resolved entry above), though `BuildMeshSection`'s own
rendering output hasn't been visually verified yet.

### [DEFERRED] Procedural material generation (asphalt, concrete, brick) and LOD system not implemented
MASTER_PROMPT Section 3.4 lists both under "Procedural Meshes." `Mesh.material`
is currently just a string name (`"asphalt"`, `"concrete"`) with no
backing material definition, parameter set (roughness/metallic per
QOL_RESEARCH_CHECKLIST.md Section D.2), or LOD levels -- there is no
rendering phase yet to consume any of that, and UE5 material assets can't
be authored/verified without the engine installed. Revisit in Phase 4+
once there's an actual UE5 project to define materials in.

### [RESOLVED] Building mesh had no roof geometry beyond a flat cap
Was: `MeshFactory.build_building_mesh` extruded every building's
rectangular footprint straight up with a flat roof quad regardless of
type -- no pitched/hipped roof or other architectural detail.

Resolved (partially -- see below) by `_gable_roof_mesh_parts`:
RESIDENTIAL buildings (see the `BuildingType` entry above) now get a
real gable (pitched) roof -- ridge along the footprint's longer
horizontal axis (matching how real gable roofs are always oriented),
peak `RESIDENTIAL_ROOF_HEIGHT_METERS` (2.5m, a fixed rise rather than one
proportional to footprint size, matching how a real gable roof's rise
doesn't scale with floor area) above the flat-roof-equivalent eave
height. MIXED_USE/COMMERCIAL buildings keep the original flat cap --
real low/mid-rise commercial buildings are overwhelmingly flat-roofed,
so this is a deliberate type-driven choice, not an oversight. 10
vertices (8 box corners + 2 ridge peaks), 16 true triangles (not
fan-triangulated quads, since the 2 gable-end faces are triangular by
construction). Every triangle's outward-normal orientation was verified
directly (for both the ridge-along-x and ridge-along-y footprint cases,
plus the square tie-breaking case) in `test_mesh_factory.py`.

Still deferred: hipped roofs, parapets, roof overhang, and any other
architectural detail beyond a single gable shape -- MASTER_PROMPT gives
no building-detail spec to implement against, and a single reasonable
shape per type is enough to close the "flat cap regardless of type" gap
without inventing an open-ended architectural taxonomy nobody asked for.

### [RESOLVED] Lane connectivity across intersections was not implemented
Was: deferred twice -- Phase 2's `lane_topology.py` deferred it to Phase
3's traffic rules; Phase 3's `traffic_network.py` deferred it again
("full per-lane turn graphs are deferred further still"), since neither
phase had (or needed) the geometric classification logic to determine
which incoming lane legally feeds which outgoing lane at an intersection.

Resolved by `src/procedural/lane_connectivity.py`
(`LaneConnectivityGenerator`): for every (incoming edge, outgoing edge)
pair at a node (from `RoadNode.incoming_edges`/`outgoing_edges`, already
populated since Phase 1 but otherwise unused for this purpose), classifies
the movement STRAIGHT/LEFT/RIGHT from the signed angle between the
incoming edge's final heading and the outgoing edge's initial heading,
excludes U-turns (`outgoing_edge is incoming_edge.reverse_edge_id`), and
drops LEFT/RIGHT movements the incoming edge's own
`allows_turning_left`/`allows_turning_right` flag forbids -- both fields
existed, unused, since Phase 1 too. Lane-level (not just edge-level)
mapping follows `lane_topology.py`'s own right-hand-traffic convention
(lane 0 = median/left lane, highest index = curb/right lane): STRAIGHT
connects lanes index-for-index, LEFT only connects lane 0 to lane 0,
RIGHT only connects the outermost lane to the outermost lane -- a
defensible default absent any dedicated-turn-lane concept elsewhere in
this codebase.

Wired into `ScenarioResult.lane_connectivity` and `ScenarioValidator`
(basic regression checks: every connection's lane ids are real, no
lane connects to itself) alongside every other generator's output.
Deliberately still out of scope: this produces a connectivity *graph*
(which lane can legally reach which), not vehicle routing/path-following
behavior -- `ActorPlacementGenerator` still places vehicles statically at
spawn zones; nothing consumes this graph to actually move a vehicle
through an intersection yet. Revisit if/when vehicle animation/routing
is ever built -- this graph is exactly what that would need as its input.

### [DEFERRED] No parking spawn zones
MASTER_PROMPT Section 3.4 lists "spawn zones (driving, parking,
pedestrian)"; only driving and pedestrian are implemented.
`ScenarioType.PARKING_LOT`'s own geometry (parking stall lattice,
`configs/scenario_templates/parking_lot.yaml`'s `lattice_spacing_m` field)
isn't generated by any module yet -- there's nothing to place parking
spawn zones against. Revisit once parking-lot-specific layout generation
exists (not currently scoped to any phase in MASTER_PROMPT beyond the
taxonomy entry in Section 1.3).

### [DEFERRED] Master prompt Section 3.3 (Phase 2) has no algorithms, formulas, code, or tests -- unlike Phase 1
MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md's Phase 2 section is
literally four bullet points per sub-area (lane topology, building
placement) plus a one-line "Tests:" list of topics, with a note saying
"(Similar structure to Phase 1, with extensive mathematical formulations
and tests)" that is never actually delivered. This is a real gap in the
spec itself. `lane_topology.py` and `building_placement.py` were designed
from scratch this phase, informed by QOL_RESEARCH_CHECKLIST.md Section B.2
(lane boundaries) and B.3 (building placement), which do give concrete
formulas/example tests (with two more bugs of their own -- see Resolved).

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

### [RESOLVED] Building types/materials were not assigned
Was: MASTER_PROMPT Section 3.3 lists "assign building types, heights,
materials" -- heights were implemented (sampled from
`config.building_heights`); building *type* and *materials* were not,
deferred until the mesh factory existed to consume them.

Resolved by `building_placement.py`'s `BuildingType` enum (RESIDENTIAL /
MIXED_USE / COMMERCIAL -- a taxonomy of this module's own invention,
since the spec gives none) and `_classify_building_type`: each
building's type is derived from where its own sampled height falls
*relative to* `config.building_heights`'s `(min, max)` range (bottom
third RESIDENTIAL, middle third MIXED_USE, top third COMMERCIAL), not a
fixed absolute threshold -- necessary because that range varies
enormously across scenario templates (a parking lot's tallest building
is shorter than urban_dense's shortest), so only a relative split means
the same thing across every scenario type. A degenerate range (`min ==
max`) defaults to MIXED_USE rather than dividing by zero. Material is
then sampled per building from `BUILDING_MATERIALS_BY_TYPE`, a small
hand-picked plausible set per type (not an exhaustive real-world
taxonomy). `mesh_factory.py`'s `build_building_mesh` now uses
`building.material` instead of a hardcoded `"concrete"` string.
`Building.building_type`/`material` both default (`MIXED_USE`/
`"concrete"`, matching the old hardcoded behavior exactly) so every
pre-existing `Building(...)` call site across the test suite kept
working unchanged.

### [DEFERRED] Heavy/optional dependencies not yet in `pyproject.toml`
`open3d==0.17.0`, `ray==2.9.3`, `h5py==3.10.0`, `protobuf==4.25.1`,
`sphinx==7.2.6` + theme/mermaid ext, `py-spy`, `memory-profiler`,
`line-profiler` are specified in MASTER_PROMPT Section 2.2 but were left out
of Phase 0's `pyproject.toml` to keep the initial install fast and because
nothing in Phase 0-1 imports them.
**Needed by**: `open3d`/`h5py` — Phase 5 (sensors/ground truth); `ray` — Phase 6
distributed generation; `protobuf` — Phase 6 custom export; `sphinx*` — Phase 8
docs; profilers — whenever performance work starts.
**Action**: add to `pyproject.toml` in the phase that first imports them, then
re-run `poetry lock` and verify no version conflicts (open3d in particular has
had NumPy 2.x incompatibilities historically — must verify against pinned
NumPy 1.26.3).

### [RESOLVED] UE5 C++ plugin skeleton was unverified — now compiled and loaded for real
Was: `unreal_plugin/SyntheticDataGen/` structurally looked like standard
UE5 module boilerplate but had never been opened in Unreal Editor or
compiled, since no UE5 install existed in any environment this project
had been built in.

Resolved 2026-09-15: a real UE 5.4.4 install + Visual Studio 2022
toolchain was set up, the plugin was compiled, and it loads cleanly
into the editor with no errors. Two real bugs were found and fixed in
the process (an `FColor`/`FLinearColor` mismatch in
`CreateMeshSection`'s call site; a missing `ProceduralMeshComponent`
plugin dependency declaration) -- see the "[RESOLVED] UE5 plugin
compiled and loaded" entry above for full detail. Confirms the risk
this entry predicted ("Build.cs dependency names... could be subtly
wrong in ways only the UE5 toolchain would catch") was real, not
hypothetical.

### [RESOLVED] No actual UE5 `.uproject` / editor project created
Was: MASTER_PROMPT 3.1.1 calls for creating the UE5 project itself via
`RunUAT.sh BuildProject`; not done since no UE5 was installed anywhere
this project had been worked on.

Resolved 2026-09-15: a real host C++ project now exists at
`F:\UE5Projects\VantageCV_UE5\` (created via the editor's New Project
flow rather than `RunUAT BuildProject`, since that's the normal
interactive path and nothing required the automated one specifically)
with `unreal_plugin/SyntheticDataGen/` installed into its `Plugins/`
folder and compiling successfully.

### [RESOLVED] CI workflow (`.github/workflows/lint_and_test.yml`) had never actually run on GitHub Actions
Was: written to spec and known to work locally via Poetry, but never
exercised on an actual Actions runner, with open questions about
`poetry install`/codecov behaving differently there.

Resolved since Phase 7 (see the `pkg_resources`/Ray entry below, found via
a real Actions run on commit `4c06f02`): every push since has run on
GitHub Actions and is confirmed green, including every commit through
`434378e` (CLI + config loader). This entry was left stale for several
commits after that -- a reminder to keep this file in sync with reality,
not just append to it.

### [DEFERRED] Docker/Kubernetes deployment (MASTER_PROMPT Section 2.4) not started
Not needed until Phase 6+ distributed/cloud scaling. No action needed yet.

### [DEFERRED] Sphinx documentation site (`docs/`) is an empty directory with only `.gitkeep`
MASTER_PROMPT 3.1.3 lists `docs/conf.py`, `index.rst`, etc. Deferred to
Phase 8 (Documentation & Release) per the roadmap — premature to scaffold
Sphinx before there's any API surface to document.

### [BLOCKER-for-later] Delaunay-based `RoadNetworkGenerator` cannot handle (near-)collinear node layouts — breaks the Highway scenario category
Discovered while chasing a coverage gap in Phase 1: `scipy.spatial.Delaunay`
raises `QhullError` ("Initial simplex is flat") whenever all input points are
exactly collinear, which `road_network.py::_connect_nodes` now catches and
re-raises as `ValueError` (see `test_collinear_points_raise_value_error_not_qhull_error`
in `tests/unit/test_road_network.py`).
**Why this matters**: MASTER_PROMPT Section 1.3 Category 3 (Highway) is
explicitly defined as "only parallel edges (no intersections)" — i.e.
nodes laid out in straight lines. The current grid-perturbation step adds
Gaussian noise that makes *exact* collinearity astronomically unlikely, so
generic urban-style bounds/config won't hit this — but a straight highway
segment's own generation logic (not yet written; belongs later in Phase 1
scenario-type-specific generation or Phase 2) will need either (a) a
non-Delaunay connectivity strategy for parallel/highway layouts, or (b) a
guaranteed transverse jitter large enough to keep Qhull's simplex
non-degenerate while staying visually "straight."
**Action**: do not reuse generic `RoadNetworkGenerator._connect_nodes`
unmodified for `ScenarioType.HIGHWAY` without addressing this. Revisit when
implementing scenario-type-specific road generation.

### [RISK] `_find_or_create_node` is O(N) per call / O(N^2) total for grid merging
Documented in its own docstring as an acceptable tradeoff at the scenario
sizes targeted (hundreds of nodes), confirmed fine by
`test_large_scenario_performance` (2000m x 2000m bounds completes well
under the 10s budget). Revisit with a `scipy.spatial.KDTree` if/when Phase
1 performance tests are run at the "10,000+ scenarios" scale mentioned in
MASTER_PROMPT's scalability requirements, or if bounds grow past ~5km.

### [DEFERRED] City-block identification approximates blocks as individual surviving Delaunay triangles
`BuildingPlacementGenerator._identify_blocks` reuses the same Delaunay
triangulation `RoadNetworkGenerator` computes internally and treats each
triangle whose 3 edges all survived length-filtering as one "block."
Real city blocks are usually quadrilateral-ish regions spanning several
adjacent triangles, not single triangles -- a general planar-graph
face-finding algorithm (walking the graph to recover actual bounded faces)
would be more realistic but is substantially more work than anything else
specified for this phase (which gives no algorithm at all -- see above).
This approximation is geometrically valid (triangles are simple,
non-overlapping polygons that correctly partition the interior) but will
produce visibly triangular block shapes rather than rectangular ones.
Revisit if/when a mesh-rendering phase makes block shape visually matter.

## Resolved

### [RESOLVED] Root `ARCHITECTURE.md` was stale — Phase 8
Written in Phase 0, before `RoadNetworkGenerator` switched from
`numpy.random.RandomState` to `numpy.random.Generator`/`PCG64` (Phase 1,
to support the master prompt's own `2**63-1` seed test requirement).
`ARCHITECTURE.md` still claimed every generator used `RandomState`,
silently wrong since Phase 1. Replaced with a short pointer to the new
`docs/architecture.rst`, which reflects the system as actually built
across all 7 completed phases (and is far more likely to be kept current
going forward, since it's part of the Sphinx build every push now
implicitly re-checks via `test_docs_build.py`).

### [RESOLVED] Sphinx docs (deferred since Phase 0) now built, and real bugs in the docstrings it exposed — Phase 8
Added the Sphinx toolchain (`sphinx`, `sphinx-rtd-theme`,
`sphinxcontrib-mermaid`) and wrote `docs/conf.py` +
`{index,api_reference,user_guide,architecture,performance_tuning,
release_notes}.rst`. API reference pages are generated by `autodoc` +
`napoleon` directly from this codebase's own (already-thorough)
docstrings -- no hand-duplicated API docs to drift out of sync.
Building surfaced two real problems, neither hypothetical:
(1) `napoleon`'s default "Attributes" rendering for dataclasses
(`RoadNode`, `BoundingBox3D`, `LidarConfig`, etc.) collided with
`autodoc`'s own separate documentation of the same fields, producing 20+
literal "duplicate object description" warnings on the first build --
fixed via `napoleon_use_ivar = True`;
(2) `segmentation.py`'s `rasterize_instance_masks` docstring's
hand-written `Returns` type text (`Dict[int, npt.NDArray[np.bool_]]`)
got parsed by napoleon as an attempted cross-reference and broke the
build with `ERROR: Unknown target name: "np.bool"` -- fixed by wrapping
it in double-backtick literal formatting instead of relying on
napoleon's automatic type-role conversion for that line, and by
switching `autodoc_typehints` from `"description"` to `"signature"`
globally to avoid this whole class of issue recurring for other type
annotations. Final state: `sphinx-build -b html` succeeds with **zero**
warnings (`-W` mode, warnings-as-errors, passes clean), verified via a
real test (`test_docs_build.py::test_docs_html_build_succeeds`), not a
one-off manual run.
`docs/user_guide.rst`'s code examples are real `.. doctest::` blocks --
every printed value was verified by actually running the example script
first (not guessed), then `sphinx-build -b doctest` genuinely executes
all 13 of them on every test run via
`test_docs_build.py::test_docs_doctest_examples_execute_correctly`. This
directly satisfies MASTER_PROMPT Section 3.9's own "Documentation builds
without errors" and "Code examples in docs execute correctly" test
bullets as real, CI-enforced checks, not documentation that could
silently drift stale.

### [RESOLVED] CI failed on Phase 7's first push: `ModuleNotFoundError: No module named 'pkg_resources'` inside Ray — root cause confirmed via user-provided log
`main` commit `4c06f02` (Phase 7) went red on GitHub Actions' `test` job
despite passing locally against a genuinely fresh clone on this machine.
This session had no way to fetch the actual failure log itself (repo API
returned `403 Must have admin rights to Repository`, no `gh` auth
available, no Docker to reproduce Ubuntu locally) -- an initial fix
attempt (capping `ray.init(object_store_memory=...)` against the
well-known "small `/dev/shm` on CI" Ray failure mode) was applied as a
reasonable but unconfirmed hypothesis and did **not** fix it. The user
then pasted the actual CI log, which showed the real error: every
`ray.remote(...).remote()` call failed with
`ModuleNotFoundError: No module named 'pkg_resources'`, raised from deep
inside `ray/_private/pydantic_compat.py`'s unconditional
`from pkg_resources import packaging` (triggered the first time Ray sets
up its serialization context for a submitted task).
Root cause: `pkg_resources` ships as part of `setuptools`, and
`setuptools` was never declared as an explicit dependency anywhere in
this project -- it was only present by transitive/environment accident,
and evidently absent (or present without `pkg_resources`) in whatever
`setuptools` version the CI runner's poetry-managed venv actually got.
Attempting the straightforward fix (`poetry add setuptools`) made it
**worse**: it resolved to the newest available `setuptools` (84.0.0),
which -- confirmed by reproducing the exact same
`ModuleNotFoundError: No module named 'pkg_resources'` locally after that
install -- has itself now removed `pkg_resources` entirely, as part of
setuptools' own ongoing deprecation of that API (import warns "slated
for removal as early as 2025-11-30"). Fixed by pinning `setuptools<81`
(landed on 80.10.2), the last major line confirmed locally to still ship
an importable `pkg_resources` (with the deprecation warning, not an
error). Verified for real: `tests/integration/test_distributed_runner.py`
(the exact 3 tests that failed in CI) now pass locally, and the full
290-test suite plus lint/mypy all pass clean.
**Process note**: this took two attempts precisely because the first fix
was applied without ever seeing the real error -- a plausible, well-
justified guess is not a substitute for the actual log. Logged honestly
as a hypothesis at the time (see the entry that used to be here); once
the user provided the real traceback, the actual fix took one attempt.
See the two [RISK] entries above (setuptools pin fragility, Ray's own
future `pkg_resources` removal) for what could still break this later.

### [RESOLVED] Resumable generation produced colliding annotation IDs across scenarios — found in Phase 7
`resume_handler.py`'s checkpoint design writes each scenario's COCO
contribution to its own small JSON "part" file via
`export_coco([frame])`, called independently per scenario. Since
`coco_exporter.export_coco`'s annotation-ID counter starts at 1 for every
call, every part file's own annotations restarted numbering at 1 --
merging parts naively produced multiple annotations across different
scenarios/images sharing the same `id`, a direct violation of
QOL_RESEARCH_CHECKLIST.md Section H.1's "no ID collisions" check (which
`coco_exporter.py`'s own tests already enforce for the *non*-resumable
path, but this manual reconstruction bypassed that guarantee). Caught
directly: `test_resumable_generation_from_scratch_matches_sequential`
failed with mismatched annotation dicts differing only in `id`, and
tracing it down confirmed actual ID collisions, not just a numbering
offset. Fixed by renumbering every annotation's `id` sequentially
immediately after merging all parts, regardless of whether each part was
freshly generated or loaded from a prior run -- bbox/segmentation/category
content is untouched, only the `id` field changes. Verified via
`test_checkpoint_restores_correctly_after_simulated_crash`, which
confirms a crashed-then-resumed run produces byte-identical output
(including annotation IDs) to an uninterrupted run.

### [RESOLVED] Added `pycocotools` and `pandas-stubs` dev dependencies — Phase 6
`pycocotools==2.0.7` installed cleanly on Windows (pre-built wheel
available) and is used for real schema validation of COCO exports
(`test_coco_schema_valid_per_pycocotools` loads the export through the
actual reference `pycocotools.coco.COCO` parser, not just hand-written
structural checks). `pandas-stubs` was added rather than reaching for
the same `ignore_missing_imports` blanket-override pattern used for
scipy (Phase 1) -- pandas has a well-maintained stubs package, so
`sanity_checker.py`'s pandas usage gets real `mypy --strict` type
checking instead of being waved through.

### [RESOLVED] Bare `poetry run pytest` doesn't discover brand-new source files until `poetry install` is re-run — found in Phase 5
Confirmed by direct, repeated testing: after adding a new file under
`src/` (e.g. `src/sensors/camera_model.py`), `poetry run pytest
tests/unit/test_camera_model.py` failed with `ModuleNotFoundError: No
module named 'src.sensors.camera_model'`, even though `.venv/Scripts/
python.exe -m pytest` (same venv, same test) and `poetry run python -m
pytest` both succeeded immediately. Existing (previously-added) test
files were unaffected by bare `poetry run pytest` -- only brand-new
modules triggered it. Root cause not fully diagnosed (something about how
the `pytest.exe` console-script entry point resolves the editable
install's package contents differs from `python -m pytest`), but running
`poetry install` again reliably fixed it every time it was tried.
**Action**: run `poetry install` after adding any new file under `src/`,
before trusting a bare `poetry run pytest` run of tests that import it.
`python -m pytest` (or `poetry run python -m pytest`) appears unaffected
and can be used as a workaround if `poetry install` is inconvenient.

### [RESOLVED] Road network nodes could end up outside the caller's declared bounds — found via Phase 4's ScenarioValidator
Discovered by `ScenarioValidator`'s own first real end-to-end test
(`test_full_generated_scenario_is_valid`) actually failing on a routine
generated scenario: node positions up to ~70m outside a 500m-wide bounds
region. Root cause, present since Phase 1 and never previously tested:
(1) `_generate_grid_points` can overshoot the requested bounds by up to
one full grid `spacing` per axis by construction (`np.arange(x_min, x_max
+ spacing, spacing)` always includes `x_min + spacing`, previously noted
in this file only as a "grid points guaranteed >= 2 per axis" quirk, not
recognized as a bounds violation in its own right); (2) Gaussian
perturbation in `_perturb_grid` can push any point further out, with no
containment check anywhere in the pipeline. Fixed by adding
`RoadNetworkGenerator._keep_within_bounds`, called after perturbation:
reflects any out-of-bounds point back across the violated edge (not a
hard clip, which would collapse every overshooting point on the same
side onto one exact boundary line -- for 3+ points, an exactly collinear
configuration that crashes Delaunay triangulation, a real failure mode
already established via `test_collinear_points_raise_value_error_not_qhull_error`).
A final `np.clip` is kept as a safety net for the practically-unreachable
case where reflection alone isn't enough. Verified with
`test_all_node_positions_within_bounds` and a 20-seed parametrized
variant, plus the originally-failing validator integration test now
passing.

### [RESOLVED] Forward/reverse road edges got independently-sampled, often-mismatched lane counts — found in Phase 3
QOL_RESEARCH_CHECKLIST.md Section G.1's own `test_lane_count_consistent`
asserts a directed edge and its reverse counterpart must have the same
`num_lanes`. Checked directly against Phase 1's `_assign_road_attributes`
(unchanged since Phase 1, not previously tested for this property): 76 of
118 edges in a routine urban_dense/500m test scenario had mismatched
forward/reverse lane counts, road types, and speed limits, because the
master prompt's reference implementation (and this codebase's Phase 1
port of it) samples each directed edge's attributes independently. Fixed
in `road_network.py::_assign_road_attributes` by computing attributes
once per undirected road and applying them identically to both directed
edges of a bidirectional pair, tracked via a `processed_edge_ids` set.
Added `test_forward_reverse_edge_attributes_match` as a regression test.
This mattered enough to fix now (rather than deferring) because Phase 3's
`TrafficNetworkGenerator` builds spawn zones and a navigation graph
directly on top of `num_lanes`/`speed_limit_kmh` -- building on
inconsistent data would have baked the bug one layer deeper.

### [RESOLVED] QOL checklist's own `test_lane_boundary_perpendicular` example asserts the wrong property — Phase 2
QOL_RESEARCH_CHECKLIST.md Section B.2 gives an example test asserting the
*boundary polyline's own segment direction* is perpendicular to the
*centerline's segment direction* (`dot(c_dir, l_dir) ~ 0`). Verified
empirically against a correct parallel-offset boundary implementation:
the actual dot product comes out ~0.9999 (nearly parallel), not ~0 --
which makes sense, since a road's edge line runs *alongside* its
centerline, not perpendicular to it. This is a bug in the checklist's own
example, not in the implementation. `math_utils.py`'s
`compute_lane_boundaries` and its tests (`test_math_utils.py`) implement
and check the actually-correct properties instead: the boundary is
parallel to a straight centerline, and the *offset vector* (boundary
point minus centerline point) is perpendicular to the local direction at
unambiguous (endpoint) points.

### [RESOLVED] Building placement took >10s and never reliably terminated in reasonable time — Phase 2
First implementation of `BuildingPlacementGenerator.generate` hung for
over a minute on a routine urban_dense/500m bounds test case (confirmed by
direct timing, not assumed). Root causes, both real and stacked: (1)
`target_count` per block sometimes reached the hundreds for a single large
triangle, and the loop paid the full `MAX_PLACEMENT_ATTEMPTS_PER_BLOCK`
cost even long after a block was effectively full; (2) every placement
candidate was checked for overlap against *every building placed in every
block so far* (`existing_buildings`), an unnecessary O(total_buildings^2)
cost across the whole scenario, not just within one block. Fixed with (1)
an early-exit after `MAX_CONSECUTIVE_FULL_FAILURES` consecutive slots each
exhaust every attempt (signal a block is full without exhausting
`target_count`), and (2) checking new candidates only against the current
block's own `placed` list -- justified because Delaunay triangle interiors
never overlap and (once the setback bug below was also fixed) no building
can cross into a neighboring block, so cross-block overlap is
geometrically impossible without an explicit check. Verified: 769
buildings generated in 0.52s post-fix vs. >60s (killed) before, on the
identical scenario.

### [RESOLVED] Road setback check missed roads passing near the *middle* of a building's side — Phase 2
While fixing the above, restricting the setback check to only a block's
own 3 triangle edges (for speed) caused `test_no_building_within_road_setback`
to actually fail: a building's corner came within 1.81m of a road,
violating the 2.0m `ROAD_SETBACK_METERS`. Root cause: for a
skinny/obtuse Delaunay triangle, a road segment that is *not* one of that
triangle's own 3 edges can still pass within the setback distance of a
point deep inside it. Fixing that (checking every real road segment,
spatially pre-filtered by a cheap padded-AABB test for speed) then
exposed a second, independent bug: the setback check itself only tested
distance from the building footprint's 4 *corners* to each road segment,
which misses a road running near-parallel to, and close beside, the
*middle* of one of the footprint's sides -- confirmed as the actual cause
of `test_no_building_to_building_overlap` failing (two buildings on
opposite sides of a shared road overlapped because neither one's corners,
specifically, were close enough to trip the corner-only check). Fixed by
replacing the corner-distance check with `_segment_intersects_aabb`
(slab-method segment-vs-box intersection) against the footprint's AABB
inflated by the setback distance -- the geometrically correct formulation
of "does anything about this road come within `ROAD_SETBACK_METERS` of
this box." Both tests now pass; see
`test_segment_intersects_aabb_near_parallel_to_one_side` for a test that
specifically reproduces the missed case.

### [RESOLVED] `tests/performance/` untracked by git — broke CI on first push
Phase 0's `.gitkeep`-placeholder pass (adding placeholders so empty
scaffold directories survive git, which doesn't track empty dirs) missed
`tests/performance/`. It existed on local disk the whole time — created
during scaffolding and never deleted — so every local test run before this
found it and passed, masking the problem entirely. A fresh `git clone`
(exactly what GitHub Actions does) never had it, so
`test_required_directory_exists[tests/performance]` failed there, which
surfaced as the "Lint and Test / test" check going red on the first push
(commit `a70a381`) while "lint" passed. Fixed by adding
`tests/performance/.gitkeep` (commit `fefdccc`) and verifying by cloning
the repo to a clean temp directory and re-running the exact CI command
(`poetry run pytest --cov=src --cov-report=xml --cov-fail-under=90
tests/`) before pushing — confirmed 69/69 pass there before trusting it.
**Process takeaway**: "tests pass locally" is not sufficient evidence for
a scaffold/structure test suite when the working tree has accumulated
directories across a session — a local run can pass on stale disk state
that git never actually captured. From here on, verify state-sensitive
test suites (anything checking file/directory existence) against a fresh
clone, not just the in-place working tree, before pushing.

### [RESOLVED] Coverage gate now exercised against real logic — Phase 1
The Phase 0 note about `--cov-fail-under=90` only being checked against an
empty `src/` tree is stale: `road_network.py` (199 stmts) and `scenario.py`
(48 stmts) now exist, and `poetry run pytest --cov=src` reports 97% overall
(96% on road_network.py) — a real, non-vacuous pass of the 90% bar. Verified
via `poetry run pytest --cov=src --cov-report=term-missing`, not just CI.

### [RESOLVED] `ScenarioTypeConfig`/`ScenarioType` were referenced but never defined in the master prompt
MASTER_PROMPT Section 3.2.2's test fixtures construct
`ScenarioTypeConfig(...)` and Section 3.1.3's file tree lists
`src/procedural/scenario.py`, but the document never actually defines
either the `ScenarioType` enum or the `ScenarioTypeConfig` schema/fields —
a genuine gap in the spec itself, not something I overlooked. Filled in
`src/procedural/scenario.py`: a `ScenarioType` str-enum matching Section
1.3's six categories, and a pydantic `ScenarioTypeConfig` model with the
fields implied by the fixtures (`avg_block_size`, `num_intersections`,
`building_density`, `vehicle_mix`, etc.), plus validators for range
ordering, density bounds, and vehicle-mix-sums-to-1. Covered by
`tests/unit/test_scenario.py` (14 tests, 100% coverage).

### [RESOLVED] `np.random.RandomState` seed range too small for the master prompt's own test requirement — Phase 1
The master prompt's Section 3.2.2 `test_seed_coverage_edge_cases` requires
`seed=2**63-1` to work, but confirmed by direct test:
`np.random.RandomState(2**63 - 1)` raises `ValueError: Seed must be between
0 and 2**32 - 1`. This is a genuine bug in the master prompt's own
reference implementation, not a hypothetical. Fixed in
`RoadNetworkGenerator.__init__` by switching to
`np.random.Generator(np.random.PCG64(seed))`, which accepts arbitrary-size
non-negative integer seeds via `SeedSequence` while remaining fully
deterministic. Verified: `test_seed_coverage_edge_cases` now passes for
seeds `[0, 42, 12345, 2**32-1, 2**63-1]`.

### [RESOLVED] Dataclass default `__eq__` crashes on numpy-array fields — Phase 1
Confirmed by direct test: a `@dataclass` with a `numpy.ndarray` field raises
`ValueError: The truth value of an array with more than one element is
ambiguous` on `==` comparison, because the generated `__eq__` chains
per-field `==` with `and`. The master prompt's `RoadNode`/`RoadEdge`
dataclasses have `position`/`centerline` ndarray fields and a custom
`__hash__`, but don't disable the default `__eq__` — meaning any code path
that compares two instances (e.g. `in` on a list, or an assertion) would
crash. Fixed by declaring both `@dataclass(eq=False)`; identity is via
`node_id`/`edge_id` through the manual `__hash__` only, and no code path
needs value-equality on these objects.

### [RESOLVED] Node/intersection classification used raw directed-edge degree instead of road-connection count — Phase 1
Found while investigating a coverage gap (the `degree == 3` T-junction
branch was never hit by any test). Root cause: every road is always
created as a *bidirectional pair* of directed edges
(`_create_edge_pair`), so `len(incoming_edges) + len(outgoing_edges)` is
**always even** for every node — the master prompt's own
`degree == 3 -> T_JUNCTION` condition is therefore mathematically
unreachable, and its `degree >= 4 -> FOUR_WAY` condition silently
mislabels genuine 3-way intersections (which have degree 6) as four-way.
Confirmed empirically: sampling degrees across a generated network showed
only even values (4, 6, 8, 10, ...), never 3. Fixed in
`_assign_road_attributes` by classifying on `degree // 2` (the actual
number of distinct connected roads) instead of raw degree. Added
`test_three_way_junction_classified_as_t_junction` and strengthened
`test_node_types_assigned_correctly` to assert degree is always even before
halving it. This also changes `_assign_road_attributes`' lane/speed
heuristic, which used the same (buggy) raw-degree comparison for its
`start_degree >= 3` branch.

### [RESOLVED] `scipy.spatial.qhull.QhullError` import path is deprecated
`from scipy.spatial.qhull import QhullError` (used in some scipy example
code and easy to reach for) emits a `DeprecationWarning` on scipy 1.11.4 —
confirmed by direct import test. Used `from scipy.spatial import
QhullError` instead (the supported public path).

### [RESOLVED] `mypy --strict` had no path for scipy (no py.typed marker) or bare `np.ndarray` — Phase 1
scipy 1.11.4 ships no type stubs, so any module importing `scipy.spatial`
failed `--strict` with `import-untyped`. Added a `[[tool.mypy.overrides]]`
block in `pyproject.toml` scoped to `module = "scipy.*"` with
`ignore_missing_imports = true`. Separately, bare `np.ndarray` field/return
annotations failed `type-arg`; replaced with `numpy.typing.NDArray[np.float64]`
throughout `road_network.py`.

### [RESOLVED] `poetry install --no-root` left `import src` unresolvable in the test venv — Phase 1
Phase 0 ran `poetry install --no-root` (to skip installing the project
itself as a package, since there was no code in `src/` yet worth
installing). Once `tests/conftest.py` added a shared fixture that imports
`from src.procedural.scenario import ...`, pytest failed with
`ModuleNotFoundError: No module named 'src'` — the poetry venv never had
the project's own package installed. Fixed by running plain `poetry
install` (no `--no-root`), which installs `synthetic-av-dataset-gen`
itself in editable mode per `pyproject.toml`'s `packages = [{include =
"src"}]`. Contributors setting up fresh should use `poetry install`, not
`--no-root`, from Phase 1 onward.

### [RESOLVED] Poetry install/lint/test flow — Phase 0
Original entry said Poetry wasn't installed and the flow was unverified.
Installed Poetry 1.7.1 via `pip install --user`, ran `poetry install`
(succeeded, `poetry.lock` generated and committed), then `poetry run pytest
--cov=src` (33/33 pass) and `scripts/run_linter.sh` (black/isort/pylint/mypy
--strict all clean, pylint 10.00/10) — all against the real Poetry-managed
environment, not just a bare pip venv.
**Residual note**: `poetry` was not on PATH after a `pip install --user` on
this Windows machine; `scripts/run_linter.sh` now falls back to
`python -m poetry` when the `poetry` executable isn't found. Contributors on
other machines should confirm `poetry` resolves normally, or rely on the
fallback.
**Update (Phase 4)**: partway through this session, `python` on PATH
started resolving to this project's own `.venv/Scripts/python.exe`
(created for early Phase 0 experimentation) instead of the system Python
that actually has Poetry installed -- so `python -m poetry` itself broke
(`No module named poetry`), even though the fallback logic above was
designed for the opposite problem (poetry missing from PATH, not python
resolving to the wrong installation). Cause not fully diagnosed (likely
some shell/session state change unrelated to this repo). Worked around by
invoking Poetry via its full system path
(`C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python.exe -m
poetry ...`) directly rather than trusting `python -m poetry`. Anyone
hitting `No module named poetry` should check `where python` first -- it
may not be the interpreter Poetry is installed against.

### [RESOLVED] pylint/mypy never run against real code — Phase 0
`tests/unit/test_project_initialization.py` initially had 8 missing-docstring
warnings and one import-outside-toplevel warning (pylint score 7.56/10).
Fixed by adding a one-line docstring to every test function and moving the
`toml` import to module level. Now 10.00/10, mypy --strict clean.
