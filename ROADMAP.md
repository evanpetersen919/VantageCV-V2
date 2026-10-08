# Roadmap

Written 2026-10-07, after 1.1. Every step below names the question it answers and the result that would
change what happens next, in the same way the experiments in [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md) do.
The evidence behind the ordering comes from desk research (competitor pages, papers' abstracts, repositories)
and from this project's own results. Claims from the research that were not checked against a primary source are
marked as such in the log entries that use them.

## Where things stand

- Synthetic images added to 25% real BDD100K data raise AP by about +2.8 (three seeds), evenly across weather,
  time of day and scene type. The gain shrinks as real data grows, and about a quarter of it disappears when the
  detector's input is raised from 960 to 1280 px.
- Truck and bus AP did not respond to any of five generator changes (1.1). The cause is in the detector and the
  data (small boxes are missed, medium and large trucks are called cars), not in what the generator draws.
- With the same scenes and no synthetic pedestrians, car and truck AP are unchanged: the vehicle results do not
  depend on the City Sample crowd, which is where the person gain comes from.
- In CARLA (`carla_loop/`), exact perception gives 0.46 collisions per km and either trained detector 1.5 to 1.8.
  The two detectors are not separable at 20 routes x 3 weights seeds. The test is underpowered, not negative.
- Waiting on Epic: whether City Sample's crowd characters (adapted from MetaHumans) may be used for training.
  Asked 2026-10-05. No datasets or weights are published until there is an answer.

## What this project is for

A static, honest generator and research log for synthetic driving data, paired with CARLA as the closed-loop
judge. Not a full learned driving stack (that needs multi-GPU training beyond this hardware), and not a
competitor to the commercial LiDAR, radar and digital-twin platforms. The project's strongest asset is that its
numbers are reproducible and its negative results are written down.

The split between the two simulators: VantageCV stays static (labelled images). Anything that moves (sequences,
tracking, optical flow, vehicle physics) belongs to CARLA and is not rebuilt here.

## Next steps, in order

1. **Housekeeping and the Epic answer.** Publish the 1.1 release page, decide on making the repository public,
   and put the Epic check-in dates in a calendar: a follow-up on 2026-10-19 if there is no reply, and a decision
   deadline of 2026-12-04 (60 days), after which silence is treated as "no".
   *If Epic says yes in writing:* release renders and weights with their wording. *If no or silence:* code and
   metrics only, and the clean-room path below is the only way to release data.
2. **1.2: more labels from what already exists.** Export 3D boxes (KITTI, nuScenes and Waymo-style files; the
   boxes are computed internally today) and pixel-exact instance and semantic masks. Estimated 2 to 5 days.
   *Question:* are the exports valid in the standard devkits, and do they convert correctly (checked with the
   existing overlay tools)? Not a claim about detector accuracy.
3. **Two controls that make the science credible.**
   - *Matched comparison with an existing synthetic dataset* (SHIFT, Synscapes or Virtual KITTI 2) at the same 512
     images, same recipe, three seeds. *Question:* does this pipeline matter, or does any extra synthetic data
     help the same amount? Reading rule fixed before the run.
   - *A better-powered CARLA test:* tracking between the detector and the agent, a breakdown of each collision
     (missed vehicle, wrong range, late detection), a sweep of detectors of different quality (to show the loop
     can see an AP effect at all), more routes, and a safety-aware metric next to collisions.
     *Question:* how much of the gap from exact perception to a detector does tracking close, and can this setup
     detect an AP difference of the size seen on real photos?
4. **Decide, from the results of step 3:** depth and normals (needs a UE capture spike under the D3D11 mode this
   machine requires), a CPU LiDAR from the existing ray-casting module (only with a concrete downstream use;
   real LiDAR benchmarks are non-commercial), and a Rocketbox pedestrian prototype (only if Epic's answer or
   deadline makes the crowd unusable).

## Not doing, and why

- **A big new training batch.** Doubling the synthetic set added about +0.9 AP at best, the gain shrinks with real
  data, and nothing can be published before Epic answers.
- **More truck and bus generator experiments.** Five levers are closed (see the 1.1 notes). What remains is a larger
  truck population, which needs many licensed models for an uncertain gain.
- **Moving actors, sequences and optical flow in VantageCV.** CARLA already does this.
- **A learned full-stack driving model** (TransFuser-class). Multi-GPU training, beyond this hardware.
- **LiDAR or radar physics, digital twins, a hosted platform.** Commercial vendors own these.

## Open dependencies

- **Epic's answer** (above).
- **CARLA versions:** the harness runs on 0.9.16. The public closed-loop benchmarks (Leaderboard 2.0, Bench2Drive)
  need 0.9.15, so using them means a second install and a modular agent, and results do not transfer between
  versions. CARLA 0.10 (UE5.5) lacks most of the maps.
- **Third-party assets:** the box truck from a Fab pack used in the v11 test carries the same "Allows usage with
  AI: No" tag as City Sample; keep it out of anything released.
