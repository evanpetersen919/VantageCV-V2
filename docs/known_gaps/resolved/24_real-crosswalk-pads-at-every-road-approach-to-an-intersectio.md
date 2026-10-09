### [RESOLVED] Real crosswalk pads at every road approach to an intersection
Follow-up to the entry above's "Not done" note: `src/procedural/
crosswalks.py`'s `generate_crosswalk_pieces` places the real, already-
migrated `SM_ROAD_19_3_0_19_crosswalk` mesh (from `Kit_City_Road`) at
each end of every physical road, flush against the paved intersection
fill's own boundary (same `compute_node_clearance` value both use),
stretched (a real per-instance `FacadePiece.scale`) to the road's own
exact combined lane width, not a separate guess.

**Two real defects found and fixed via live verification, not assumed
away**: (1) the mesh's genuine ~56cm road-crown geometry, placed
unscaled onto this project's deliberately flat road, rendered as a
visible ridge across every crosswalk -- confirmed via screenshot, fixed
with a small flattening Z-scale (`CROSSWALK_Z_SCALE`). (2) The mesh's
own material (`M_Asphalt_Master_Inst_Crosswalk`) was assumed to carry
baked-in zebra striping; dumping its actual texture references from the
migrated `.uasset` showed only generic asphalt/concrete/puddle textures,
and an isolated in-engine test spawn confirmed a plain toned pad, not a
stripe pattern. Cross-checked against real Epic placement data (not
just this one material) via a headless CitySample Python query: 566 real
crosswalk pad instances from the `CITY_ground` point cloud, correlated
against 11,103 nearby line-decal instances from the `CITY_decals` point
cloud (`SM_White_Line_00_inst`/`SM_White_Road_Line_00_inst`) -- no
repeating perpendicular-stripe pattern coincident with any real pad's
own footprint, only a thin stop-line built from many small dash segments
at the pad's road-side edge plus ordinary dashed lane-divider segments
that happened to fall within the search radius. Real Epic crosswalks in
this kit are genuinely just the toned pad, not a painted zebra pattern.

**Follow-up (same day)**: the plain toned pad, while real and correctly
placed, didn't read as "a crosswalk" to a viewer at normal shot distances
-- user-reported after seeing it live. Rather than guess at a zebra
pattern Epic's own data doesn't support, `generate_crosswalk_pieces` now
also emits a real stop-line piece per end, using `SM_White_Line_00_inst`
(from `Kit_MeshDecals_A`, already migrated). The real dash count/spacing
Epic's own instances use looked hand-placed/jittered per intersection,
not a derivable formula, so this doesn't try to replicate that exactly --
an honest simplification, not a guess. What IS reused directly: across
every real dash instance found near a pad edge, `scale_y` was `0.12` in
12 of 14 samples (the clear mode); combined with the mesh's own measured
unscaled size (`GetStaticMeshBounds`: a flat 512x512cm square), that
gives a real stripe thickness of `512cm * 0.12 = 61.4cm` -- within a
centimetre of the standard real-world 24in crosswalk stripe width, not a
coincidence. One continuous bar (not Epic's own irregular dashes) is
built at that real thickness, stretched to the crossing's own real
width, at the exact same pivot/rotation as its pad, lifted 1cm to avoid
z-fighting. Verified live: a crisp, continuous white stop-line now spans
each crosswalk approach, flush on the pavement, clearly readable as a
real crossing marker.

**Follow-up (same day): continental/ladder markings, plus a real
placement bug found from live feedback**. The toned pad was dropped
entirely (its distinct tint still read as an unrealistic "different
shade of road" even after the stop-line was added), and the single
stop-line was replaced with the published continental/"ladder"
crosswalk pattern both the FHWA MUTCD (3B.18) and NYC DOT Street Design
Manual define -- parallel bars running WITH the direction of travel,
not one line across it -- since Epic's own decal placements were too
irregular to reverse-engineer a pattern of their own. Bar width stays
the same real, measured 61.4cm value found earlier. Crossing depth was
increased from the real crosswalk tile's 3.0m nominal length to 3.75m,
derived (not guessed) from Fruin's pedestrian shoulder-width figure used
in Highway Capacity Manual pedestrian LOS work (~0.75m/person x 5 people
abreast).

While implementing this, live review surfaced a real math bug, not a
taste issue: `SM_White_Line_00_inst` is pivoted at its own mesh CENTER
(`GetStaticMeshBounds`: origin `(0,0,0)`, symmetric `+-256cm` extent),
unlike the earlier pad mesh, which was edge-pivoted. The first version
of the ladder bars reused the pad's edge-pivot placement math (bar pivot
at `clearance + depth`), which for a centre-pivoted mesh actually
centres the bar there instead -- leaving a real, unintended `depth / 2`
gap between the crosswalk and the intersection pavement's edge (the
"not close enough to intersection" the user reported). Fixed by
centring each bar at `clearance + depth / 2`, so the near edge lands
exactly on `clearance` and the far edge at `clearance + depth`. The
existing tests only checked the bar's pivot, which is why they didn't
catch it; added `test_bar_extent_is_exactly_flush_with_the_intersection
_pavement`, which reconstructs the actual rendered edge positions from
the pivot and scale and checks both edges directly -- this is the kind
of invariant a pivot-only test can miss even when it passes. Verified
live: crosswalks now sit flush against the intersection with no gap,
and each bar is visibly longer/wider, matching the "room for five
people to cross abreast" target.

