"""Measure this project's geometric labels against the engine's exact ones (game running).

    PYTHONPATH=. python bin/audit_labels.py --focus truck --scenarios 12 --out results/audit.json

For each scenario a hero vehicle of the ``--focus`` type is chosen, the scene is cut to what lies
within 50 m of it, and the camera is placed at ego-like height around it. Per object, the labels
``render_frame`` makes (full box, visible-part box, polygon) are compared with what the game
renders (``CaptureObjectMasks``): box IoU against the full extent, box IoU against the visible
extent, and polygon IoU against the visible mask. Per-object rows go to ``--out``; a summary per
class is printed.
"""

# pylint: disable=too-many-arguments,too-many-locals

import argparse
import asyncio
import dataclasses
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.export.masks import rasterise
from src.orchestration.dataset_generator import generate_scenario, render_frame
from src.orchestration.exact_labels import capture_exact
from src.orchestration.live_render import LiveRenderer, ue_camera
from src.orchestration.scenario_serializer import object_asset_indices, serialize_scenario
from src.procedural.environment import TimeOfDay, Weather, scenario_environment
from src.ue5.backend import UE5Backend
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
SIZE = (1920, 1080)
CLASS_NAMES = {2: "sedan", 3: "suv/pickup/van", 4: "truck", 5: "bus", 6: "person"}
Box = Tuple[float, float, float, float]


def box_iou(a: Box, b: Box) -> float:
    """Intersection over union of two (x0, y0, x1, y1) boxes."""
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0.0, width) * max(0.0, height)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _pixel_box(values: List[int]) -> Box:
    """An engine extent (inclusive pixel indices) as an (x0, y0, x1, y1) box."""
    return (float(values[0]), float(values[1]), float(values[2] + 1), float(values[3] + 1))


def _local_scenario(scenario: Any, hero: Any, radius: float) -> Any:
    centre = np.asarray(hero.box_center, dtype=np.float64)
    vehicles = [
        v for v in scenario.vehicles if np.linalg.norm(np.asarray(v.box_center) - centre) < radius
    ]
    people = [
        p for p in scenario.pedestrians if np.linalg.norm(np.asarray(p.center) - centre) < radius
    ]
    return dataclasses.replace(scenario, vehicles=vehicles, pedestrians=people)


def _object_rows(
    frame: Any, amodal: Any, exact: Any, ours_mask: Any, view: Dict[str, int]
) -> List[Dict[str, Any]]:
    """One row per object the game rendered: how far each of our labels is from the engine's."""
    by_id = {box.object_id: box for box in amodal.bboxes_2d}
    rows: List[Dict[str, Any]] = []
    for k, object_id in enumerate(exact.order):
        report = exact.reports[k]
        row: Dict[str, Any] = {
            **view,
            "object": object_id,
            "category": frame.bboxes_3d_by_id[object_id].category_id,
        }
        if report.get("actors_found", 0) == 0 or report.get("amodal_px", 0) == 0:
            rows.append({**row, "note": "no actor or nothing rendered"})
            continue
        row["visible_share"] = report["visible_px"] / report["amodal_px"]
        full = by_id.get(object_id)
        if full is not None:
            row["iou_full_box"] = box_iou(
                (full.x_min, full.y_min, full.x_max, full.y_max), _pixel_box(report["amodal_bbox"])
            )
        modal = next((b for b in frame.bboxes_2d if b.object_id == object_id), None)
        if modal is not None and report["visible_px"] > 0:
            row["iou_visible_box"] = box_iou(
                (modal.x_min, modal.y_min, modal.x_max, modal.y_max),
                _pixel_box(report["visible_bbox"]),
            )
            truth, mine = exact.visible_map == k + 1, ours_mask == k + 1
            union = int((truth | mine).sum())
            row["iou_polygon"] = float((truth & mine).sum() / union) if union else 0.0
        rows.append(row)
    return rows


async def _audit_view(
    backend: Any,
    local: Any,
    members: Dict[int, List[int]],
    position: Any,
    target: Any,
    out: Path,
    view: Dict[str, int],
) -> List[Dict[str, Any]]:
    renderer_camera = ue_camera(position, target, *SIZE)
    frame = render_frame(local, renderer_camera, 1, "x.png", modal=True)
    amodal = render_frame(local, renderer_camera, 1, "x.png", modal=False)
    exact = await capture_exact(backend, members, frame, SIZE, out.parent / "audit_tmp.u16")
    if exact is None:
        return []
    annotations = [
        {
            "id": k,
            "category_id": 1,
            "segmentation": []
            if frame.silhouettes_by_id.get(object_id) is None
            else [frame.silhouettes_by_id[object_id].flatten().tolist()],
            "box3d": {
                "location": [
                    0,
                    0,
                    float(np.linalg.norm(frame.bboxes_3d_by_id[object_id].center - position)),
                ]
            },
        }
        for k, object_id in enumerate(exact.order)
    ]
    ours_mask, _, _ = rasterise(annotations, SIZE)
    return _object_rows(frame, amodal, exact, ours_mask, view)


async def audit(
    config_path: str, focus: str, scenarios: int, views: int, seed: int, out: Path
) -> List[Dict[str, Any]]:
    """Audit ``scenarios`` scenarios from ``seed``, ``views`` camera positions each."""
    config = load_scenario_config(config_path)
    rows: List[Dict[str, Any]] = []
    async with UE5Backend("ws://localhost:8765", timeout_seconds=300.0) as backend:
        renderer = LiveRenderer(backend, settle_seconds=0.5, load_seconds=15.0)
        for index in range(scenarios):
            scenario = generate_scenario(
                seed + index, config, BOUNDS, f"audit{seed + index}", time_of_day=TimeOfDay.DAY
            )
            heroes = [v for v in scenario.vehicles if v.vehicle_type == focus]
            if not heroes:
                continue
            local = _local_scenario(scenario, heroes[0], 50.0)
            environment = scenario_environment(
                local.season, TimeOfDay.DAY, Weather.OVERCAST, seed + index, "v7"
            )
            payload = serialize_scenario(local, environment)
            await renderer.load(payload)
            members = object_asset_indices(local, payload)
            centre = np.asarray(heroes[0].box_center, dtype=np.float64)
            for view in range(views):
                angle, radius = np.radians(40.0 + 100.0 * view), 12.0 + 5.0 * view
                position = np.array(
                    [centre[0] + radius * np.cos(angle), centre[1] + radius * np.sin(angle), 1.6]
                )
                target = np.array([centre[0], centre[1], 1.0])
                await renderer.capture(position, target, out.parent / "audit_tmp.png")
                rows += await _audit_view(
                    backend,
                    local,
                    members,
                    position,
                    target,
                    out,
                    {"scenario": index, "view": view},
                )
    return rows


def summarise(rows: List[Dict[str, Any]]) -> None:
    """Print per-class means of the three measures."""
    by_class: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_class[row["category"]].append(row)
    print(f"{len(rows)} objects")
    for category, items in sorted(by_class.items()):

        def mean(key: str, items: List[Dict[str, Any]] = items) -> Optional[float]:
            values = [r[key] for r in items if key in r]
            return float(np.mean(values)) if values else None

        def fmt(value: Optional[float]) -> str:
            return "  n/a" if value is None else f"{value:.3f}"

        count = sum("iou_full_box" in r for r in items)
        print(
            f"{CLASS_NAMES.get(category, category):15s} n={count:4d}  "
            f"full box {fmt(mean('iou_full_box'))}  "
            f"visible box {fmt(mean('iou_visible_box'))}  polygon {fmt(mean('iou_polygon'))}"
        )


def main() -> None:
    """Parse arguments, audit, write the rows, print the summary."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--config", default="configs/scenario_templates/urban_dense_v7_peds.yaml")
    parser.add_argument("--focus", default="sedan", choices=["sedan", "suv", "truck", "bus"])
    parser.add_argument("--scenarios", type=int, default=8)
    parser.add_argument("--views", type=int, default=3)
    parser.add_argument("--seed", type=int, default=70010)
    parser.add_argument("--out", type=Path, default=Path("results/label_audit.json"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = asyncio.run(
        audit(args.config, args.focus, args.scenarios, args.views, args.seed, args.out)
    )
    args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    summarise(rows)


if __name__ == "__main__":
    main()
