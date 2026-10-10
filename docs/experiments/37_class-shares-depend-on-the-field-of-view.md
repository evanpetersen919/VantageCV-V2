## Class shares depend on the field of view (2026-10-10)

Entry 34 left the building share high (28% against 21% in Cityscapes validation) and the sky share too (7% against 3%).
The first reading was a scene problem (building heights, setbacks). This entry checks the camera first, because a share
is a property of a view, not of a scene alone.

**The field of view.** The game renders at the engine's fixed field of view: 90 degrees at a 4:3 reference aspect, which
is a 73.74 degree vertical field and, at 16:9 (1920 x 1080), a **106 degree horizontal field**
(`src/orchestration/live_render.py`). The recorded intrinsics follow from it. A dashcam or the Cityscapes camera sees much
less: Cityscapes' published intrinsics (fx about 2262 px for a 2048 px wide frame) give about **48 degrees horizontal and
26 degrees vertical**. That value is the dataset's published figure; the camera files are not in the local copy, so it was
not re-measured here. BDD100K's field of view is not recorded in the local labels and was not measured.

**Experiment.** A pinhole image cropped about its centre is exactly the image of a narrower field of view (with fewer
pixels). Class maps of 16 frames (8 forced-summer v17 scenes, two views each) were cropped to the field of view named and
the share of labelled pixels of each class recomputed (`demo/` script, not tracked; the 16 frames are the entry 34
set).

| Field of view (h x v) | road | sidewalk | building | vegetation | sky | car | person |
|---|---|---|---|---|---|---|---|
| Full frame, 106 x 74 (as rendered) | 30.5 | 7.5 | **28.0** | 15.7 | 7.2 | 6.1 | 0.5 |
| 70 x 43 | 31.3 | 6.4 | 19.0 | 21.6 | 6.1 | 9.4 | 0.3 |
| 60 x 36 | 30.9 | 5.8 | 16.9 | 22.9 | 5.9 | 10.7 | 0.4 |
| 48 x 26 (Cityscapes) | 28.3 | 5.1 | 14.1 | 24.8 | 5.6 | 14.5 | 0.5 |
| **Cityscapes val (measured)** | 38.2 | 5.5 | 20.9 | 17.1 | 3.3 | 6.2 | 1.3 |

**Reading.**
- The building share is not simply a matter of too much building: at a field of view near a real camera's it falls to
  14 to 19%, below the real 20.9%, while vegetation (centred on the street) and cars (central and near) rise well above
  real. So the wide field *redistributes* the classes: it adds facade at the edges and spreads the central ones.
- No single view reproduces all the real shares at once. At 70 x 43 buildings are close (19.0 against 20.9) but vegetation
  (21.6 against 17.1) and cars (9.4 against 6.2) are over. The crop is a rough device: it keeps our camera's pitch and
  height and ignores that a narrower real camera would have been aimed differently.
- Cars at 6.1% in the full frame look right only because they are small in a wide frame; the detector benchmarks care
  about object scale, and the box-size distributions in earlier entries were matched at this field of view by fitting
  distance cutoffs.

**What this does and does not change.**
- It does *not* show that a narrower field of view would improve detector transfer; nothing here trains anything.
- It does mean the building and sky shares are a poor target for scene changes (new buildings, different heights) until
  the camera is settled, and I did not add buildings.
- Changing the field of view would alter every pixel scale in every earlier batch (the cutoffs, box statistics and results
  are all at 106 x 74), so it is a decision to take deliberately, with its own pre-registered comparison, not as a
  polish step. The depth and mask captures already accept a field of view; the screenshot path uses the engine's fixed
  one, so the RGB frame would need a small plugin change.

**Open.** Whether to render a v18 batch at a narrower field and compare detectors, and with what real field of view
(measure BDD100K's from its intrinsics if available), is unresolved.
