# pylint: disable=line-too-long
"""The dataset card, draft terms and notices written into a release folder.

Numbers in the card are measured from the folder's own annotation files, so they cannot drift from
the data; the prose states what the data are, how the labels were made, and what they are not.
The terms are a DRAFT that has not been reviewed by counsel, and say so in their first line.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict

import numpy as np
from PIL import Image

from src.evaluation.class_maps import OUR_CLASSES
from src.ground_truth.semantic_classes import CLASS_NAMES

MIT_TEXT = """MIT License

Copyright (c) 2020 Microsoft

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

TERMS = """# Dataset terms (DRAFT: not reviewed by counsel)

These terms apply to the images, annotations, depth maps and class maps in this folder.

1. **Use.** You may use, copy, modify and redistribute the dataset, including for research and for
   commercial work, provided you keep this file and `NOTICES.md` with it and credit the dataset
   (see the citation in `README.md`).
2. **No generative AI.** You may not use the dataset, or anything derived from its images, to
   train, develop or feed a generative AI program, meaning a system designed to automate the
   generation of, or aid in the creation of, new content (for example text-to-image, image-to-image
   or video generation models). The images were rendered from Unreal Engine City Sample content,
   whose licence carries a restriction of this kind.
3. **Perception models are fine.** Training and evaluating non-generative models (object
   detection, segmentation, depth estimation and the like) is permitted.
4. **No endorsement.** Nothing here is endorsed by Epic Games, Microsoft or anyone else named in
   `NOTICES.md`.
5. **No warranty.** The dataset is provided "as is", without warranty of any kind.
"""


def _stats(out: Path) -> Dict[str, Any]:
    """Counts measured from the release folder."""
    images, annotations = [], []
    for name in ("train", "val"):
        coco = json.loads(
            (out / "annotations" / f"instances_{name}.json").read_text(encoding="utf-8")
        )
        for image in coco["images"]:
            image["split"] = name
        images += coco["images"]
        annotations += coco["annotations"]
    per_class = Counter(OUR_CLASSES[a["category_id"]] for a in annotations)
    shares: Counter[int] = Counter()
    sample = images[:: max(1, len(images) // 100)]
    for image in sample:
        classes = np.array(Image.open(out / image["semantic_file"]))
        for value, count in zip(*np.unique(classes, return_counts=True)):
            shares[int(value)] += int(count)
    total = sum(shares.values())
    return {
        "images": len(images),
        "train": sum(1 for i in images if i["split"] == "train"),
        "val": sum(1 for i in images if i["split"] == "val"),
        "annotations": len(annotations),
        "per_class": dict(per_class),
        "persons_per_image": per_class["person"] / max(len(images), 1),
        "time_of_day": dict(Counter(i["time_of_day"] for i in images)),
        "weather": dict(Counter(i["weather"] for i in images)),
        "hood_share": sum(1 for i in images if i.get("hood_top_px")) / max(len(images), 1),
        "class_shares": {
            CLASS_NAMES[c]: 100.0 * n / total
            for c, n in sorted(shares.items(), key=lambda x: -x[1])
        },
        "size": (images[0]["width"], images[0]["height"]),
        "fov": images[0]["vertical_fov_deg"],
        "sample": len(sample),
    }


def _table(rows: Dict[str, Any]) -> str:
    return "\n".join(f"| {key} | {value} |" for key, value in rows.items())


def write_card(out: Path, manifest_path: Path, batch_name: str) -> Dict[str, Any]:
    """Write ``README.md``, ``DATASET_TERMS.md`` and ``NOTICES.md`` into ``out``; returns the stats."""
    stats = _stats(out)
    policy = json.loads(manifest_path.read_text(encoding="utf-8")).get("annotation_policy", {})
    distances = policy.get("max_distance_m", {})
    cutoffs = {
        "person": distances.get("6"),
        "car": distances.get("2"),
        "bus": distances.get("5"),
        "truck": distances.get("4"),
    }
    width, height = stats["size"]
    classes = "\n".join(
        f"| {c['id']} | {c['name']} | {tuple(c['color_rgb'])} |"
        for c in json.loads((out / "classes.json").read_text(encoding="utf-8"))["semantic_classes"]
    )
    shares_text = ", ".join(f"{name} {share:.1f}%" for name, share in stats["class_shares"].items())
    card = f"""# VantageCV synthetic urban driving dataset ({batch_name})

**{stats['images']:,} forward-looking driving frames** ({width}x{height}, one camera, vertical field of
view {stats['fov']:.2f} degrees) rendered in Unreal Engine 5.4 from procedurally generated city
scenes, with **exact** per-pixel annotations taken from the engine itself:

| Annotation | Files | What it is |
|---|---|---|
| 2D boxes | `annotations/instances_*.json`, `labels/` | COCO and YOLO boxes of person, car, bus, truck, tight around the visible pixels |
| Instance masks | `annotations/*.json` (`mask_rle`), `instance/` | the visible pixels of each object, run-length encoded and as 16-bit PNGs |
| Polygons | `annotations/*.json` (`segmentation`), `labels_seg/` | outlines traced along those pixels, one polygon per visible part |
| Visibility | `visibility_fraction`, `truncation` per object | share of the object that is visible, and cut by the frame edge |
| 3D boxes | `box3d` per object, `kitti/` | KITTI-convention boxes in a gravity-aligned camera frame, with `kitti_P2` per image |
| Class map | `semantic/` | full-scene class per pixel (below), 8-bit PNG, Cityscapes label ids |
| Depth | `depth/` | metric depth per pixel, 16-bit PNG: metres x 256 along the viewing axis, 0 = no surface |
| Conditions | per image in the COCO files | time of day, weather, season, camera pose, hood row |

{stats['train']:,} training and {stats['val']:,} validation images, split **by scenario** (a scene never
appears on both sides). {stats['annotations']:,} object annotations.

## Contents

| class | objects |
|---|---|
{_table({k: f'{v:,}' for k, v in stats['per_class'].items()})}

Objects are labelled out to a per-class distance in metres, {cutoffs}. About
{stats['persons_per_image']:.1f} persons per image. Time of day {stats['time_of_day']}; weather {stats['weather']}.
About {100 * stats['hood_share']:.0f}% of the frames have the ego car's hood painted across the bottom;
labels and maps treat it as `ego vehicle`.

### Full-scene classes (Cityscapes label ids)

| id | name | colour (RGB) |
|---|---|---|
{classes}

Share of pixels (measured on {stats['sample']} frames): {shares_text}.
Choices where Cityscapes is ambiguous: curbs and tree-pit grates are `sidewalk`; parking meters,
hydrants, parking blocks and bins are `static`; a road sign includes its post; lamp posts are `pole`;
roof equipment is `building`; trailers are `truck`; `sky` is wherever the engine reports no surface.
No pixel is left `unlabeled` (checked on every frame).

## How the labels were made

Each frame is rendered, then the game is asked for the scene's depth and for each group of objects
or surfaces on its own. A pixel belongs to an object where the object's own depth equals the scene's
depth (nothing nearer hides it). No proxy shapes, projections or hulls are involved. Checks run on
every release: class map against the instance masks (100% agreement), polygons against masks
(IoU about 0.997 for persons), depth against independent 3D boxes, and a validation that every
file exists and every class id is known (`bin/package_dataset.py`).

## Layout

```
images/  semantic/  depth/  instance/  instance_table/
annotations/instances_train.json  annotations/instances_val.json
labels/  labels_seg/  train.txt  val.txt  data.yaml      (YOLO; paths relative to this folder)
kitti/label_2  kitti/calib  kitti/ImageSets               (KITTI ids are the image ids; images are in images/)
classes.json  MANIFEST.json  README.md  DATASET_TERMS.md  NOTICES.md
```

```python
import json, numpy as np
from PIL import Image
from pycocotools import mask as mask_utils
coco = json.load(open("annotations/instances_val.json"))
image = coco["images"][0]
rgb = np.array(Image.open(image["file_name"]))
classes = np.array(Image.open(image["semantic_file"]))                 # Cityscapes label ids
depth_m = np.array(Image.open(image["depth_file"])).astype(float) / image["depth_scale"]  # 0 = none
annotation = next(a for a in coco["annotations"] if a["image_id"] == image["id"])
mask = mask_utils.decode({{"size": annotation["mask_rle"]["size"],
                          "counts": annotation["mask_rle"]["counts"].encode()}})
```

Training with Ultralytics: `data.yaml` is in this folder (detection labels in `labels/`; for
segmentation copy `labels_seg/` over `labels/`).

## What this is not

* **Synthetic.** The images look rendered. Models trained on them need real data too; in the
  project's own experiments a 512-image supplement raised detection AP on real photographs by about
  3 points when added to a quarter of BDD100K, and the gain is mostly from persons (details in the
  project repository, `EXPERIMENT_LOG.md`). It is not a replacement for real footage.
* **Narrow.** One town style (City Sample's buildings and vehicles), one camera, adults only as
  pedestrians (no children, riders, bicycles or motorcycles), no traffic signs beyond a no-parking
  sign, no lane-level semantics, no LiDAR or radar. Objects are labelled only out to the distances
  above and above the minimum box size ({policy.get('min_box_width_px', 4):.0f} x {policy.get('min_box_height_px', 8):.0f} px), as in the real benchmarks.
* **Polygons have no holes.** A gap enclosed by an arm and a torso is covered by the outer
  polygon; `mask_rle` and `instance/` keep it exact.
* **Depth range.** 0 to about 256 m at 1/256 m resolution; farther surfaces read 255.99.
* **Night lamp glare** (the red halo and glow around taillights and headlamps) is added in image space after
  rendering, fitted to real BDD100K night frames; the engine's own picture has no such glare. Labels are unaffected.
* **Weather and lighting** are the engine's presets (clear, overcast, rain, fog, sunset, golden hour,
  dawn haze, night), not measured distributions.

## Terms, notices, citation

`DATASET_TERMS.md` (a draft, not yet reviewed by counsel) and `NOTICES.md` (Epic Games and
Microsoft Rocketbox attributions) apply. Code, tools and the experiment log:
https://github.com/evanpetersen919/VantageCV-V2 . Cite as: Petersen, E., VantageCV Remastered:
Synthetic AV Dataset Generator, 2026 (see `CITATION.cff` in the repository).
"""
    (out / "README.md").write_text(card, encoding="utf-8")
    (out / "DATASET_TERMS.md").write_text(TERMS, encoding="utf-8")
    (out / "NOTICES.md").write_text(
        """# Notices

* **Unreal Engine and City Sample** are the property of Epic Games, Inc. The frames were rendered
  with Unreal Engine 5.4 from the City Sample project's buildings, road kit, vehicles and props
  (including Quixel Megascans items bundled with it). No Epic asset files are included in this
  dataset, only rendered images and annotations. This project is not affiliated with or endorsed by
  Epic Games.
* **Pedestrians** are Microsoft Rocketbox avatars, used under the MIT License below.
* No real-world images or data from any other dataset are included.

## Microsoft Rocketbox (MIT)

"""
        + MIT_TEXT,
        encoding="utf-8",
    )
    return stats
