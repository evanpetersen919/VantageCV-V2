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

