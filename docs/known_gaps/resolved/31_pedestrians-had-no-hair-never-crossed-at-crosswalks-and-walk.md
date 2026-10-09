### [RESOLVED] Pedestrians had no hair, never crossed at crosswalks, and walked in a single perfect line

Live feedback (screenshots) surfaced three real problems in the outfit-
variety work above, none hypothetical: (1) every pedestrian was
completely bald -- the earlier body/top/bottom/shoe/face assembly never
added a hair piece at all; combined with baldness, some faces read as
gender-ambiguous even though `PEDESTRIAN_FACE_ASSET_PATHS[gender]`
scoping was already correct (confirmed via the already-passing
`test_pedestrian_body_and_parts_are_consistent`) -- the perceived
"reversed" gender was a hair-driven illusion, not a real data bug;
(2) sidewalk pedestrians were tiled at an exact, fixed lateral offset
with identical heading, producing a visibly unnatural "tightrope" single
file; (3) zero pedestrians ever appeared on a crosswalk, despite
`crosswalks.py` painting real ladder-bar crossings at every road end.

**Hair**: `city_sample_assets.py` gained
`PEDESTRIAN_HAIR_ASSET_PATHS: Dict[Tuple[gender, char_id], Optional[str]]`
built from directly inspecting every real
`CitySample/Content/Crowd/Character/<Gender>/<id>/Hair/Hair/Hair_*.uasset`
folder -- each City Sample character has exactly ONE real canonical
hairstyle (not a random choice among several), so this is a lookup
table, not a sampled distribution. Three real, disclosed exceptions
where no matching VAT-baked hair exists: `f_008` (genuinely bald by
design -- no Hair folder at all), `m_004` (real style is
BuzzCut/PulledBack, never baked into VAT's limited 9-style set), `m_005`
(also genuinely bald by design). `pedestrian_face_and_hair(gender,
face_asset_path)` derives the character id from the face path and looks
up the real hair, reusing the same zero-new-C++ `part_paths` mechanism
as the other outfit pieces. Live-verified: hair meshes with correct,
recognizable names (`Hair_S_Pixie_Mesh`, `Hair_S_LowPonytail_Helmet`,
`Hair_S_AfroFade_Helmet`, etc.) spawn as real actors in a loaded scene.

**Two-way sidewalk traffic + lateral jitter + keep-right bias**:
`actor_placement.py` gained `PEDESTRIAN_LATERAL_JITTER_METERS = 1.0`
(real ADA/PROWAG pedestrian shy-distance figure, ~0.45-0.6m, doubled for
a visible spread rather than presented as a precise citation) and
`PEDESTRIAN_KEEP_RIGHT_BIAS_METERS = 0.4` (a reasonable, explicitly
disclosed estimate, not a cited figure -- there is no real per-scenario
pedestrian flow simulation in this project to derive it from, since
every scenario is a frozen single frame, not a running simulation; the
bias approximates real keep-right pedestrian flow statistically instead
of simulating it). Sidewalk pedestrians now pick a walking direction
each with 50% probability (facing either way along the sidewalk) and
offset laterally by `keep_right_bias + uniform(-jitter, +jitter)`, using
the already-proven-correct `compute_perpendicular` (real right-hand
convention) for the offset direction. Live-verified via real actor
positions in a loaded scene: three pedestrians tiled at the real,
exact 3.0m `PEDESTRIAN_SPAWN_GAP_METERS` spacing along one sidewalk edge
varied by up to ~1.3m laterally (previously bit-for-bit identical),
confirming the jitter/bias is real and active, not a no-op.

**Crosswalk-crossing pedestrians**: extracted `CrosswalkAnchor` /
`compute_crosswalk_anchors()` out of `crosswalks.py` so both the painted
ladder bars and the new crossing-pedestrian spawn zones read the exact
same real geometry (pivot, perpendicular, rotation, combined road
width) -- they can never drift apart, by construction, rather than
re-deriving the same math twice. `traffic_network.py`'s `SpawnZone`
gained a new `CROSSING` zone type tiled across each anchor's real road
width at the same 3.0m gap, carrying a precomputed `heading_rad` (a
crosswalk spans a whole road at a node, not one directed edge, so it has
no single `edge_id` to derive heading from at placement time -- both
fields made `Optional` to represent this honestly rather than faking an
edge). `PEDESTRIAN_CROSSING_DENSITY_FRACTION_OF_TRAFFIC = 0.1` is
another explicitly disclosed estimate (no real crossing-frequency data
was found), not a cited figure. Live-verified: real `SM_White_Line_00_inst`
crosswalk-bar actors and real pedestrian body/hair actors both present
in the same loaded scene, at the anchor positions the shared geometry
predicts.

**Explicitly deferred, not silently dropped**: the user's request also
asked about "how pedestrians are moving and what they are doing" --
pose/activity diversity (standing vs. mid-stride, phone-checking,
waiting, etc.). This project's VAT pedestrian meshes bake pose into a
material parameter (`GetFrame`, selecting a baked animation frame), but
nothing in the current static-asset spawn path (`part_paths` /
`"static_asset"` JSON) can override a per-instance material scalar
parameter -- doing this for real would need new C++ (a material-
parameter-override capability), not just new Python data. Out of scope
for this pass given the size of the hair/jitter/crossing work above;
every pedestrian in this scenario still renders in the same single
baked pose. Full suite green (558/558, +1 net test this batch).

