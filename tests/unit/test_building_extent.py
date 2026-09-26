"""Tests for the building label extent taken from the placed facade pieces."""

from pathlib import Path

import numpy as np
import pytest

from src.ground_truth.bbox_3d import extract_bbox_3d
from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_extent import building_extent, piece_corners
from src.procedural.building_facade import FacadePiece
from src.procedural.building_placement import Building
from src.procedural.facade_piece_bounds import FACADE_PIECE_BOUNDS
from src.utils.config_loader import load_scenario_config

PATH = next(iter(FACADE_PIECE_BOUNDS))
BOUNDS = (-1.0, -0.5, 0.0, 2.0, 0.5, 3.0)


def test_piece_corners_apply_position_rotation_and_scale() -> None:
    """A quarter turn swaps the x and y extents; the position translates; scale multiplies."""
    plain = piece_corners(FacadePiece(PATH, np.zeros(3), 0.0), BOUNDS)
    assert plain[:, 0].min() == pytest.approx(-1.0) and plain[:, 0].max() == pytest.approx(2.0)
    turned = piece_corners(FacadePiece(PATH, np.array([10.0, 20.0, 1.0]), np.pi / 2), BOUNDS)
    assert turned[:, 0].min() == pytest.approx(10.0 - 0.5) and turned[:, 0].max() == pytest.approx(
        10.5
    )
    assert turned[:, 1].min() == pytest.approx(20.0 - 1.0) and turned[:, 1].max() == pytest.approx(
        22.0
    )
    assert turned[:, 2].max() == pytest.approx(4.0)
    mirrored = piece_corners(FacadePiece(PATH, np.zeros(3), 0.0, scale=(1.0, -0.5, 2.0)), BOUNDS)
    assert mirrored[:, 1].min() == pytest.approx(-0.25) and mirrored[:, 1].max() == pytest.approx(
        0.25
    )
    assert mirrored[:, 2].max() == pytest.approx(6.0)


def test_building_extent_is_the_union_of_its_pieces() -> None:
    """Two pieces side by side give one extent; unmeasured pieces are ignored."""
    pieces = [
        FacadePiece(PATH, np.array([0.0, 0.0, 0.0]), 0.0),
        FacadePiece(PATH, np.array([5.0, 0.0, 3.0]), 0.0),
        FacadePiece("/Game/Not/Measured", np.array([500.0, 500.0, 500.0]), 0.0),
    ]
    extent = building_extent(pieces)
    assert extent is not None
    box = FACADE_PIECE_BOUNDS[PATH]
    assert extent[0] == pytest.approx(box[0])
    assert extent[2] == pytest.approx(5.0 + box[3])
    assert extent[4] == pytest.approx(3.0 + box[5])


def test_no_measured_pieces_gives_no_extent() -> None:
    """Without any measured piece there is nothing to take an extent from."""
    assert building_extent([FacadePiece("/Game/Not/Measured", np.zeros(3), 0.0)]) is None
    assert building_extent([]) is None


def test_label_uses_the_extent_when_present_and_the_footprint_otherwise() -> None:
    """The 3D label follows ``label_extent``; without it, the footprint and height."""
    building = Building(3, np.array([10.0, 20.0]), 8.0, 6.0, 30.0)
    plain = extract_bbox_3d(building)
    assert np.allclose(plain.dimensions, [8.0, 6.0, 30.0])
    with_extent = Building(
        3, np.array([10.0, 20.0]), 8.0, 6.0, 30.0, label_extent=(5.0, 16.0, 16.0, 24.5, 31.5)
    )
    box = extract_bbox_3d(with_extent)
    assert np.allclose(box.dimensions, [11.0, 8.5, 31.5])
    assert np.allclose(box.center, [10.5, 20.25, 15.75])


def test_generated_buildings_are_labelled_at_least_as_big_as_their_footprint() -> None:
    """Pieces reach past the footprint line, never inside it, and to or above the height."""
    config = load_scenario_config(Path("configs/scenario_templates/urban_dense.yaml"))
    scenario = generate_scenario(100, config, (-150.0, -150.0, 150.0, 150.0), "extent")
    assert scenario.buildings
    for building in scenario.buildings:
        assert building.label_extent is not None
        x_min, y_min, x_max, y_max = building.aabb
        left, bottom, right, top, height = building.label_extent
        assert left <= x_min + 1e-6 and bottom <= y_min + 1e-6
        assert right >= x_max - 1e-6 and top >= y_max - 1e-6
        assert height >= building.height - 1e-6
