### [RESOLVED] Real pedestrian outfit variety via body/top/bottom/shoe/face part assembly
User asked for real clothing/personality diversity instead of every
pedestrian wearing the same 2 fixed outfits (one per gender). Heavily
researched first (dispatched an Explore agent into `F:\UE5Projects\
CitySample`, no guessing): every gender/weight combination beyond the
original 2 pre-baked "combined" meshes exists as separate body/top/
bottom/shoe pieces, with a real structural hint (before live
verification) that they assemble like vehicle parts -- every garment
piece for one gender+weight shares exactly one bone-animation texture
pair (`TX_<gender>_tal_BonePosition/BoneRotation`), not a per-piece one,
meaning they're baked from one shared rig in one shared coordinate
frame.

**Gating verification before any migration/implementation** (this
project's established discipline): migrated 3 small test assets first
(`SM_f_tal_nrw_body`/`_jeans`/`_buttonDown`), confirmed their real
measured bounds stack sensibly (legs low, waist/hands mid, shirt above,
all sharing the same x/y origin), then confirmed live with a screenshot
showing a correctly shaped and positioned pair of jeans and a shirt on
the body -- the assembly hypothesis holds. One real gap found this way:
the bare `body` piece has no head; the face is a genuinely separate
piece (`SM_<gender>_<charID>_<weight>_FaceMesh`), fused into `combined`
but not into `body` alone.

**Full migration** (whole `Content/Crowd/VAT` folder, 4.3GB -- more than
the initially-estimated "few hundred MB" once every garment/face
texture was pulled in, still far under the 7.6GB full skeletal
`Character/` tree) confirmed the real, full combinatorial inventory by
direct file listing (not guessed): female has 9 tops x 5 bottoms x 3
shoes across 3 weights, male has 10 tops x 6 bottoms x 2 shoes; 6 face
character IDs per gender (female skips 006/007 but has 008 -- a real
asymmetry vs. the skeletal `Character/` tree's own IDs, confirmed by
direct listing, not assumed to match).

**Real, disclosed limitation found and worked around, not silently
guessed past**: pairing a specific character's `ovw`/`unw` FaceMesh
rendered as a checkerboard/missing-material in a live test; the SAME
character's `nrw` FaceMesh rendered correctly. Traced to the source, not
just patched: CitySample itself only ships ONE real normal-map texture
per face character ID (confirmed directly in CitySample's own content
tree, not a migration gap) -- there is no `ovw`/`unw` face texture to
migrate in the first place. Rather than reverse-engineer an uncertain
material-graph workaround for a texture Epic never authored, faces
always use the `nrw` variant regardless of the paired body's own weight
class. Verified live this produces no visible seam/misalignment pairing
an `nrw` face with an `ovw` body -- and it's a reasonable simplification
on real evidence, not just convenience: these bodies' own measured
bounds show weight changes body WIDTH noticeably but height/depth
barely at all, and standing height (not weight) is what a mismatched
face would most depend on.

**Implementation**: `city_sample_assets.py` gained
`PEDESTRIAN_BODY_ASSET_PATHS`/`_TOP_`/`_BOTTOM_`/`_SHOE_ASSET_PATHS`
(all keyed by real `(gender, weight)` tuples, built programmatically
from the confirmed real name lists, not hand-typed path-by-path) and
`_FACE_ASSET_PATHS` (keyed by gender only, per the `nrw`-only decision
above). `Pedestrian` gained a `part_paths: List[str]` field (top,
bottom, shoe, face -- independently sampled per instance from its own
gender+weight's real options); `_try_place_pedestrian` now samples
gender and weight class evenly (no real distribution data was found to
weight one over another, disclosed rather than silently assumed) before
sampling its outfit. `PEDESTRIAN_DIMENSIONS_METERS` is now keyed by
gender (not by a specific asset path), reusing each gender's one real
full-figure measurement across all 3 weight classes -- the same
"weight doesn't change height" evidence backs this too.
`scenario_serializer.py`'s `_pedestrian_to_asset_json` now passes
`pedestrian.part_paths` through instead of a hardcoded empty list --
zero new C++, since a `"static_asset"` category with non-empty
`part_paths` was already proven to work for vehicle wheels/doors.

Live-verified end-to-end: a real generated scenario (91 pedestrians)
produced genuinely unique, correctly-scoped outfit combinations (no
gender/weight mismatches), loaded and rendered correctly in a full city
scene alongside buildings/traffic/crosswalks. New test
(`test_pedestrian_body_and_parts_are_consistent`) checks every placed
pedestrian's body, all 4 parts, and its dimensions are mutually
consistent for its own sampled gender+weight, never a mismatch. Full
suite green (557/557).

