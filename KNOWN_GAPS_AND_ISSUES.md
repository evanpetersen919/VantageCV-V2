# Known Gaps, Risks & Open Issues

Living log of everything deferred, unverified, or risky in this implementation,
so nothing gets silently lost between sessions/phases. Update this file whenever
a gap is discovered, deferred, or closed. Never delete a closed entry — mark it
`RESOLVED` with the phase/commit that fixed it.

Severity: **BLOCKER** (must fix before shipping) / **RISK** (works but fragile,
should fix before relying on it) / **DEFERRED** (intentionally postponed to a
later phase, tracked so it isn't forgotten).

---

Every entry is its own file under [`docs/known_gaps/`](docs/known_gaps/).

## Open

| Status | Entry |
|---|---|
| DEFERRED | [3D ground-truth boxes and the LiDAR sensor model are not wired into the live pipeline or export](docs/known_gaps/open/01_3d-ground-truth-boxes-and-the-lidar-sensor-model-are-not-wir.md) |
| RESOLVED | [Horizon "ribbon" artifact -- WorldPartitionHLOD proxies, a class the terrain-hiding logic never matched](docs/known_gaps/open/02_horizon-ribbon-artifact-worldpartitionhlod-proxies-a-class-t.md) |
| VERIFIED | [Full-size (500m) scenario load: 299 buildings, ~68,000 assets, no crash](docs/known_gaps/open/03_full-size-500m-scenario-load-299-buildings-68-000-assets-no.md) |
| RESOLVED, no foliage | [Scenario seasons: winter, spring, summer, fall](docs/known_gaps/open/04_scenario-seasons-winter-spring-summer-fall.md) |
| RESOLVED | [Roofs now use Epic's own roof materials and carry rooftop equipment](docs/known_gaps/open/05_roofs-now-use-epic-s-own-roof-materials-and-carry-rooftop-eq.md) |
| RESOLVED, bare trees only | [No trees -- now street birches in tree bases along the sidewalks](docs/known_gaps/open/06_no-trees-now-street-birches-in-tree-bases-along-the-sidewalk.md) |
| RESOLVED, first pass | [Sidewalks were empty -- now real street furniture along every curb](docs/known_gaps/open/07_sidewalks-were-empty-now-real-street-furniture-along-every-c.md) |
| RESOLVED, mostly | [Buildings were open-topped -- now flat roof slabs plus real roof caps on CHH and SFA](docs/known_gaps/open/08_buildings-were-open-topped-now-flat-roof-slabs-plus-real-roo.md) |
| RESOLVED, first stage | [Roads were flat mirror-like strips with no curbs or sidewalks -- now real curbs and sidewalks, and matte asphalt](docs/known_gaps/open/09_roads-were-flat-mirror-like-strips-with-no-curbs-or-sidewalk.md) |
| RESOLVED | [Per-instance mesh scale is now supported end to end](docs/known_gaps/open/10_per-instance-mesh-scale-is-now-supported-end-to-end.md) |
| RESOLVED, one artifact left | [Every frame showed the engine template's checkerboard floor and desert hills](docs/known_gaps/open/11_every-frame-showed-the-engine-template-s-checkerboard-floor.md) |
| REFERENCE | [Building facade tiling is DONE and verified -- read this before touching `building_facade.py` again](docs/known_gaps/open/12_building-facade-tiling-is-done-and-verified-read-this-before.md) |
| RESOLVED | [Buildings were flat textured boxes -- now real modular City Sample facades (walls/corners, tiled), closing into genuine rectangles](docs/known_gaps/open/13_buildings-were-flat-textured-boxes-now-real-modular-city-sam.md) |
| RESOLVED | [Visible top-down gap at every corner turn -- root cause was NOT the corner-to-wall constant; it was two other real, now-fixed modeling errors](docs/known_gaps/open/14_visible-top-down-gap-at-every-corner-turn-root-cause-was-not.md) |
| RESOLVED | [Corner piece's own outer trim didn't wrap flush around the true vertex -- the last visible seam](docs/known_gaps/open/15_corner-piece-s-own-outer-trim-didn-t-wrap-flush-around-the-t.md) |
| RESOLVED | [Building/road mesh sections never applied a real material -- always rendered as UE5's default flat material](docs/known_gaps/open/16_building-road-mesh-sections-never-applied-a-real-material-al.md) |
| RESOLVED | [Debug/overview camera pawn could cast a visible shadow onto generated content -- misread as a broken vehicle texture](docs/known_gaps/open/17_debug-overview-camera-pawn-could-cast-a-visible-shadow-onto.md) |
| RESOLVED | [Vehicles were body-shell-only -- now fully assembled (wheels, doors, glass, interior, steering wheel)](docs/known_gaps/open/18_vehicles-were-body-shell-only-now-fully-assembled-wheels-doo.md) |
| RESOLVED | [Vehicle paint materials/textures -- real root cause found and fixed, not the MassTraffic plugin dependency it looked like](docs/known_gaps/open/19_vehicle-paint-materials-textures-real-root-cause-found-and-f.md) |
| DEFERRED | [Road network is a plain uniform grid -- reasonable for this stage, real next-step identified via research on how AV/PCG companies actually do it](docs/known_gaps/open/20_road-network-is-a-plain-uniform-grid-reasonable-for-this-sta.md) |
| RESOLVED | [Live-session dogfooding found three real bugs: vehicles invisible, inconsistent road widths, thin leftover blocks](docs/known_gaps/open/21_live-session-dogfooding-found-three-real-bugs-vehicles-invis.md) |
| RESOLVED | [Vehicles still invisible after the position fix -- two more real bugs found via actual screenshots, not logs](docs/known_gaps/open/22_vehicles-still-invisible-after-the-position-fix-two-more-rea.md) |
| RESOLVED | [City Sample asset integration Phase 0: real scenario serializer built; both asset-type investigations resolved with real evidence](docs/known_gaps/open/23_city-sample-asset-integration-phase-0-real-scenario-serializ.md) |
| RESOLVED | [City Sample asset integration Phase 1 (Python side): vehicles sample real City Sample asset paths, no longer build box meshes](docs/known_gaps/open/24_city-sample-asset-integration-phase-1-python-side-vehicles-s.md) |
| RESOLVED | [Road network rearchitected to a plain orthogonal grid -- eliminates the remaining lane-overlap z-fighting entirely](docs/known_gaps/open/25_road-network-rearchitected-to-a-plain-orthogonal-grid-elimin.md) |
| RESOLVED | [Three real UE5 rendering bugs found by actually looking at a rendered scenario (scale, handedness, missing normals)](docs/known_gaps/open/26_three-real-ue5-rendering-bugs-found-by-actually-looking-at-a.md) |
| RESOLVED | [Two real geometry-overlap bugs found via actually rendering a scenario in UE5, not any prior unit test](docs/known_gaps/open/27_two-real-geometry-overlap-bugs-found-via-actually-rendering.md) |
| DEFERRED | [No actual RGB image files are ever produced -- COCO `file_name` references a file that doesn't exist on disk](docs/known_gaps/open/28_no-actual-rgb-image-files-are-ever-produced-coco-file-name-r.md) |
| RESOLVED | [`default_overview_camera` framed scenarios poorly, leaving most of the image empty](docs/known_gaps/open/29_default-overview-camera-framed-scenarios-poorly-leaving-most.md) |
| RESOLVED | [Scenario config YAML templates were reference-only, never actually loaded](docs/known_gaps/open/30_scenario-config-yaml-templates-were-reference-only-never-act.md) |
| RESOLVED | [No CLI entry points (`bin/generate_dataset.py` etc.)](docs/known_gaps/open/31_no-cli-entry-points-bin-generate-dataset-py-etc.md) |
| DEFERRED | [No real multi-node/multi-GPU scaling test; CPU-core parallelism confirmed sub-linear, root cause still open](docs/known_gaps/open/32_no-real-multi-node-multi-gpu-scaling-test-cpu-core-paralleli.md) |
| RESOLVED | [Resumable/checkpointed generation verified via a real simulated crash, not just the mocked unit test](docs/known_gaps/open/33_resumable-checkpointed-generation-verified-via-a-real-simula.md) |
| RISK | [`pkg_resources` (needed by Ray, via the pinned `setuptools<81`) is slated for removal by setuptools upstream](docs/known_gaps/open/34_pkg-resources-needed-by-ray-via-the-pinned-setuptools-81-is.md) |
| RISK | [Ray adds meaningful test-suite startup overhead](docs/known_gaps/open/35_ray-adds-meaningful-test-suite-startup-overhead.md) |
| DEFERRED | [NuScenes format conversion not implemented](docs/known_gaps/open/36_nuscenes-format-conversion-not-implemented.md) |
| DEFERRED | [Sim2real distribution analysis not implemented](docs/known_gaps/open/37_sim2real-distribution-analysis-not-implemented.md) |
| RESOLVED | [COCO export only carried building/"structure" annotations](docs/known_gaps/open/38_coco-export-only-carried-building-structure-annotations.md) |
| RESOLVED | [LiDAR ray-casting and depth-map rendering had no spatial acceleration structure](docs/known_gaps/open/39_lidar-ray-casting-and-depth-map-rendering-had-no-spatial-acc.md) |
| RESOLVED | [`TriangleGrid.closest_hit` silently dropped real hits on flat/coplanar geometry -- found via a genuine cross-platform CI failure](docs/known_gaps/open/40_trianglegrid-closest-hit-silently-dropped-real-hits-on-flat.md) |
| RESOLVED | [Segmentation mask rasterization was O(width * height) per object](docs/known_gaps/open/41_segmentation-mask-rasterization-was-o-width-height-per-objec.md) |
| RESOLVED | [Ground truth extraction only covered buildings, not vehicles/pedestrians](docs/known_gaps/open/42_ground-truth-extraction-only-covered-buildings-not-vehicles.md) |
| RESOLVED | [No sensor noise model](docs/known_gaps/open/43_no-sensor-noise-model.md) |
| RISK | [`UE5Backend`'s per-call connection setup makes the master prompt's <100ms/<2s latency budgets unverifiable as literally stated](docs/known_gaps/open/44_ue5backend-s-per-call-connection-setup-makes-the-master-prom.md) |
| RESOLVED | [LoadProceduralScenario now dispatches real mesh sections -- verified end-to-end, visually, against a real scenario](docs/known_gaps/open/45_loadproceduralscenario-now-dispatches-real-mesh-sections-ver.md) |
| RESOLVED | [UE5 plugin compiled and loaded into a real UE 5.4.4 editor for the first time](docs/known_gaps/open/46_ue5-plugin-compiled-and-loaded-into-a-real-ue-5-4-4-editor-f.md) |
| RESOLVED | [WebSocket JSON-RPC bridge built and a real Ping round trip confirmed against a live UE5 editor](docs/known_gaps/open/47_websocket-json-rpc-bridge-built-and-a-real-ping-round-trip-c.md) |
| DEFERRED | [Master prompt Section 3.4 (Phase 3) contradicts Section 1.1 on which language owns mesh generation](docs/known_gaps/open/48_master-prompt-section-3-4-phase-3-contradicts-section-1-1-on.md) |
| DEFERRED | [Procedural material generation (asphalt, concrete, brick) and LOD system not implemented](docs/known_gaps/open/49_procedural-material-generation-asphalt-concrete-brick-and-lo.md) |
| RESOLVED | [Building mesh had no roof geometry beyond a flat cap](docs/known_gaps/open/50_building-mesh-had-no-roof-geometry-beyond-a-flat-cap.md) |
| RESOLVED | [Lane connectivity across intersections was not implemented](docs/known_gaps/open/51_lane-connectivity-across-intersections-was-not-implemented.md) |
| DEFERRED | [No parking spawn zones](docs/known_gaps/open/52_no-parking-spawn-zones.md) |
| DEFERRED | [Master prompt Section 3.3 (Phase 2) has no algorithms, formulas, code, or tests -- unlike Phase 1](docs/known_gaps/open/53_master-prompt-section-3-3-phase-2-has-no-algorithms-formulas.md) |
| RESOLVED | [`ScenarioTypeConfig` had no field for road setback](docs/known_gaps/open/54_scenariotypeconfig-had-no-field-for-road-setback.md) |
| RESOLVED | [Building types/materials were not assigned](docs/known_gaps/open/55_building-types-materials-were-not-assigned.md) |
| DEFERRED | [Heavy/optional dependencies not yet in `pyproject.toml`](docs/known_gaps/open/56_heavy-optional-dependencies-not-yet-in-pyproject-toml.md) |
| RESOLVED | [UE5 C++ plugin skeleton was unverified — now compiled and loaded for real](docs/known_gaps/open/57_ue5-c-plugin-skeleton-was-unverified-now-compiled-and-loaded.md) |
| RESOLVED | [No actual UE5 `.uproject` / editor project created](docs/known_gaps/open/58_no-actual-ue5-uproject-editor-project-created.md) |
| RESOLVED | [CI workflow (`.github/workflows/lint_and_test.yml`) had never actually run on GitHub Actions](docs/known_gaps/open/59_ci-workflow-github-workflows-lint-and-test-yml-had-never-act.md) |
| DEFERRED | [Docker/Kubernetes deployment (MASTER_PROMPT Section 2.4) not started](docs/known_gaps/open/60_docker-kubernetes-deployment-master-prompt-section-2-4-not-s.md) |
| DEFERRED | [Sphinx documentation site (`docs/`) is an empty directory with only `.gitkeep`](docs/known_gaps/open/61_sphinx-documentation-site-docs-is-an-empty-directory-with-on.md) |
| BLOCKER-for-later | [Delaunay-based `RoadNetworkGenerator` cannot handle (near-)collinear node layouts — breaks the Highway scenario category](docs/known_gaps/open/62_delaunay-based-roadnetworkgenerator-cannot-handle-near-colli.md) |
| RISK | [`_find_or_create_node` is O(N) per call / O(N^2) total for grid merging](docs/known_gaps/open/63_find-or-create-node-is-o-n-per-call-o-n-2-total-for-grid-mer.md) |
| DEFERRED | [City-block identification approximates blocks as individual surviving Delaunay triangles](docs/known_gaps/open/64_city-block-identification-approximates-blocks-as-individual.md) |

## Resolved

| Status | Entry |
|---|---|
| RESOLVED | [Root `ARCHITECTURE.md` was stale — Phase 8](docs/known_gaps/resolved/01_root-architecture-md-was-stale-phase-8.md) |
| RESOLVED | [Sphinx docs (deferred since Phase 0) now built, and real bugs in the docstrings it exposed — Phase 8](docs/known_gaps/resolved/02_sphinx-docs-deferred-since-phase-0-now-built-and-real-bugs-i.md) |
| RESOLVED | [CI failed on Phase 7's first push: `ModuleNotFoundError: No module named 'pkg_resources'` inside Ray — root cause confirmed via user-provided log](docs/known_gaps/resolved/03_ci-failed-on-phase-7-s-first-push-modulenotfounderror-no-mod.md) |
| RESOLVED | [Resumable generation produced colliding annotation IDs across scenarios — found in Phase 7](docs/known_gaps/resolved/04_resumable-generation-produced-colliding-annotation-ids-acros.md) |
| RESOLVED | [Added `pycocotools` and `pandas-stubs` dev dependencies — Phase 6](docs/known_gaps/resolved/05_added-pycocotools-and-pandas-stubs-dev-dependencies-phase-6.md) |
| RESOLVED | [Bare `poetry run pytest` doesn't discover brand-new source files until `poetry install` is re-run — found in Phase 5](docs/known_gaps/resolved/06_bare-poetry-run-pytest-doesn-t-discover-brand-new-source-fil.md) |
| RESOLVED | [Road network nodes could end up outside the caller's declared bounds — found via Phase 4's ScenarioValidator](docs/known_gaps/resolved/07_road-network-nodes-could-end-up-outside-the-caller-s-declare.md) |
| RESOLVED | [Forward/reverse road edges got independently-sampled, often-mismatched lane counts — found in Phase 3](docs/known_gaps/resolved/08_forward-reverse-road-edges-got-independently-sampled-often-m.md) |
| RESOLVED | [QOL checklist's own `test_lane_boundary_perpendicular` example asserts the wrong property — Phase 2](docs/known_gaps/resolved/09_qol-checklist-s-own-test-lane-boundary-perpendicular-example.md) |
| RESOLVED | [Building placement took >10s and never reliably terminated in reasonable time — Phase 2](docs/known_gaps/resolved/10_building-placement-took-10s-and-never-reliably-terminated-in.md) |
| RESOLVED | [Road setback check missed roads passing near the *middle* of a building's side — Phase 2](docs/known_gaps/resolved/11_road-setback-check-missed-roads-passing-near-the-middle-of-a.md) |
| RESOLVED | [`tests/performance/` untracked by git — broke CI on first push](docs/known_gaps/resolved/12_tests-performance-untracked-by-git-broke-ci-on-first-push.md) |
| RESOLVED | [Coverage gate now exercised against real logic — Phase 1](docs/known_gaps/resolved/13_coverage-gate-now-exercised-against-real-logic-phase-1.md) |
| RESOLVED | [`ScenarioTypeConfig`/`ScenarioType` were referenced but never defined in the master prompt](docs/known_gaps/resolved/14_scenariotypeconfig-scenariotype-were-referenced-but-never-de.md) |
| RESOLVED | [`np.random.RandomState` seed range too small for the master prompt's own test requirement — Phase 1](docs/known_gaps/resolved/15_np-random-randomstate-seed-range-too-small-for-the-master-pr.md) |
| RESOLVED | [Dataclass default `__eq__` crashes on numpy-array fields — Phase 1](docs/known_gaps/resolved/16_dataclass-default-eq-crashes-on-numpy-array-fields-phase-1.md) |
| RESOLVED | [Node/intersection classification used raw directed-edge degree instead of road-connection count — Phase 1](docs/known_gaps/resolved/17_node-intersection-classification-used-raw-directed-edge-degr.md) |
| RESOLVED | [`scipy.spatial.qhull.QhullError` import path is deprecated](docs/known_gaps/resolved/18_scipy-spatial-qhull-qhullerror-import-path-is-deprecated.md) |
| RESOLVED | [`mypy --strict` had no path for scipy (no py.typed marker) or bare `np.ndarray` — Phase 1](docs/known_gaps/resolved/19_mypy-strict-had-no-path-for-scipy-no-py-typed-marker-or-bare.md) |
| RESOLVED | [`poetry install --no-root` left `import src` unresolvable in the test venv — Phase 1](docs/known_gaps/resolved/20_poetry-install-no-root-left-import-src-unresolvable-in-the-t.md) |
| RESOLVED | [Poetry install/lint/test flow — Phase 0](docs/known_gaps/resolved/21_poetry-install-lint-test-flow-phase-0.md) |
| RESOLVED | [pylint/mypy never run against real code — Phase 0](docs/known_gaps/resolved/22_pylint-mypy-never-run-against-real-code-phase-0.md) |
| RESOLVED | [Paved intersection surface closes the lane-trim gap](docs/known_gaps/resolved/23_paved-intersection-surface-closes-the-lane-trim-gap.md) |
| RESOLVED | [Real crosswalk pads at every road approach to an intersection](docs/known_gaps/resolved/24_real-crosswalk-pads-at-every-road-approach-to-an-intersectio.md) |
| RESOLVED | [Real traffic signal poles at every intersection approach](docs/known_gaps/resolved/25_real-traffic-signal-poles-at-every-intersection-approach.md) |
| RESOLVED | [Real pedestrians via City Sample's VAT crowd meshes, replacing box placeholders](docs/known_gaps/resolved/26_real-pedestrians-via-city-sample-s-vat-crowd-meshes-replacin.md) |
| RESOLVED | [Pedestrian sidewalk spawn density, sourced from City Sample's own real crowd config](docs/known_gaps/resolved/27_pedestrian-sidewalk-spawn-density-sourced-from-city-sample-s.md) |
| RESOLVED | [Pedestrians were walking 90 degrees off the sidewalk, and standing at road level not sidewalk level](docs/known_gaps/resolved/28_pedestrians-were-walking-90-degrees-off-the-sidewalk-and-sta.md) |
| RESOLVED | [Occasional pedestrians standing in the road at intersections](docs/known_gaps/resolved/29_occasional-pedestrians-standing-in-the-road-at-intersections.md) |
| RESOLVED | [Real pedestrian outfit variety via body/top/bottom/shoe/face part assembly](docs/known_gaps/resolved/30_real-pedestrian-outfit-variety-via-body-top-bottom-shoe-face.md) |
| RESOLVED | [Pedestrians had no hair, never crossed at crosswalks, and walked in a single perfect line](docs/known_gaps/resolved/31_pedestrians-had-no-hair-never-crossed-at-crosswalks-and-walk.md) |
| RESOLVED | [Pedestrian pose/activity diversity, and the real reason the obvious fix didn't render anything](docs/known_gaps/resolved/32_pedestrian-pose-activity-diversity-and-the-real-reason-the-o.md) |
| RESOLVED | [Crossing pedestrians floated above the road; most pedestrians looked like they were standing still](docs/known_gaps/resolved/33_crossing-pedestrians-floated-above-the-road-most-pedestrians.md) |
| RESOLVED | ["Always standing then walking, in sync" persisted after the first fix -- real root cause was the range itself, not animation](docs/known_gaps/resolved/34_always-standing-then-walking-in-sync-persisted-after-the-fir.md) |
| RESOLVED | [Reversed the curated-window fix above: full real walk cycle + a real "standing" activity for dataset capture, plus an opt-in live-preview animation for interactive QA](docs/known_gaps/resolved/35_reversed-the-curated-window-fix-above-full-real-walk-cycle-a.md) |
| RESOLVED | [Pedestrians visibly walk/idle-cycle in Play mode even on the real, non-live-preview dataset-capture path](docs/known_gaps/resolved/36_pedestrians-visibly-walk-idle-cycle-in-play-mode-even-on-the.md) |
| OPEN, NOT RESOLVED -- paused after a real regression | [Traffic-light pole color can't be safely driven yet](docs/known_gaps/resolved/37_traffic-light-pole-color-can-t-be-safely-driven-yet.md) |
