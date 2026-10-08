"""Instance and semantic masks, and the KITTI folder written from a generated dataset."""

# pylint: disable=missing-function-docstring,duplicate-code

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.export.coco_exporter import export_coco
from src.export.masks import rasterise
from src.orchestration.dataset_generator import generate_scenario, render_frame
from src.orchestration.live_render import ue_camera
from src.utils.config_loader import load_scenario_config

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "bin" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _square(annotation_id: int, category: int, origin: tuple, side: float, depth: float) -> dict:
    x, y = origin
    corners = [x, y, x + side, y, x + side, y + side, x, y + side]
    return {
        "id": annotation_id,
        "category_id": category,
        "segmentation": [corners],
        "box3d": {"location": [0.0, 1.0, depth]},
    }


def test_a_nearer_object_covers_a_farther_one_whatever_the_order_of_the_annotations() -> None:
    far = _square(10, 3, (10, 10), 40, depth=50.0)
    near = _square(11, 1, (30, 30), 40, depth=10.0)
    for annotations in ([far, near], [near, far]):
        instance, semantic, table = rasterise(annotations, (100, 100))
        index = {t["annotation_id"]: t["instance"] for t in table}
        assert (
            instance[45, 45] == index[11] and semantic[45, 45] == 1
        )  # the overlap belongs to the near one
        assert instance[15, 15] == index[10] and semantic[15, 15] == 3
        assert instance[90, 90] == 0 and semantic[90, 90] == 0


def test_an_unoccluded_instance_has_the_pixel_area_of_its_polygon() -> None:
    instance, _, _ = rasterise([_square(1, 1, (20, 20), 50, depth=5.0)], (200, 200))
    assert (instance == 1).sum() == pytest.approx(50 * 50, rel=0.05)  # edges are inclusive


def test_an_annotation_without_a_box_counts_as_the_farthest() -> None:
    plain = {"id": 1, "category_id": 2, "segmentation": [[0, 0, 60, 0, 60, 60, 0, 60]]}
    near = _square(2, 1, (20, 20), 30, depth=3.0)
    instance, _, table = rasterise([plain, near], (100, 100))
    assert instance[30, 30] == next(t["instance"] for t in table if t["annotation_id"] == 2)
    assert instance[5, 5] == next(t["instance"] for t in table if t["annotation_id"] == 1)


def test_kitti_folder_from_generated_frames(tmp_path: Path) -> None:
    config = load_scenario_config("configs/scenario_templates/urban_dense_v8a.yaml")
    frames = []
    for number, seed in enumerate((70000, 70001), start=1):
        scenario = generate_scenario(seed, config, (-150.0, -150.0, 150.0, 150.0), f"t{seed}")
        centre = np.asarray(scenario.vehicles[0].box_center, dtype=np.float64)
        camera = ue_camera(
            np.array([centre[0] - 6.0, centre[1] - 6.0, 1.6]),
            np.array([centre[0], centre[1], 1.0]),
            1280,
            720,
        )
        frames.append(render_frame(scenario, camera, number, f"img{number}.png"))
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "annotations.json").write_text(json.dumps(export_coco(frames)), encoding="utf-8")

    counts = _load("export_kitti").export_kitti(dataset, tmp_path / "kitti")
    assert counts["images"] == 2 and counts["boxes"] > 3
    for stem in ("000001", "000002"):
        for line in (tmp_path / "kitti" / "label_2" / f"{stem}.txt").read_text().splitlines():
            parts = line.split()
            assert len(parts) == 15 and parts[0] in ("Car", "Truck", "Misc", "Pedestrian")
            assert all(np.isfinite(float(p)) for p in parts[1:])
        calib = (tmp_path / "kitti" / "calib" / f"{stem}.txt").read_text().splitlines()
        assert [c.split(":")[0] for c in calib][:3] == ["P0", "P1", "P2"]
    assert (tmp_path / "kitti" / "ImageSets" / "all.txt").read_text().split() == [
        "000001",
        "000002",
    ]


def test_overview_frames_are_skipped_not_exported_wrongly(tmp_path: Path) -> None:
    dataset = tmp_path / "d"
    dataset.mkdir()
    (dataset / "annotations.json").write_text(
        json.dumps(
            {
                "images": [{"id": 1, "file_name": "a.png", "width": 10, "height": 10}],
                "annotations": [],
                "categories": [{"id": 1, "name": "car"}],
            }
        ),
        encoding="utf-8",
    )
    counts = _load("export_kitti").export_kitti(dataset, tmp_path / "out")
    assert counts["images"] == 0 and counts["skipped_images"] == 1
