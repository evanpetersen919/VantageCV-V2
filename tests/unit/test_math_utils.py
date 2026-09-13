"""Unit tests for math_utils.py geometric helpers.

Note: QOL_RESEARCH_CHECKLIST.md Section B.2's own example test
(``test_lane_boundary_perpendicular``) asserts the boundary polyline's own
segment direction is perpendicular to the centerline's segment direction
(dot ~ 0). Empirically this is backwards: a geometrically correct
parallel-offset boundary runs *alongside* the centerline, so its direction
is nearly parallel to the centerline's (dot ~ 1), not perpendicular. See
KNOWN_GAPS_AND_ISSUES.md. The tests below check the actually-correct
properties: boundary direction is parallel to centerline direction, and
the *offset vector* (boundary point minus centerline point) is
perpendicular to it.
"""

import numpy as np
import pytest

from src.procedural.math_utils import compute_lane_boundaries, compute_perpendicular


def test_compute_perpendicular_is_unit_length() -> None:
    """The result is a unit vector for any non-degenerate input."""
    perp = compute_perpendicular(np.array([3.0, 4.0]))
    assert np.isclose(np.linalg.norm(perp), 1.0)


def test_compute_perpendicular_right_hand_orientation() -> None:
    """Rotating [1, 0] by -90 degrees gives [0, -1]."""
    perp = compute_perpendicular(np.array([1.0, 0.0]))
    assert np.allclose(perp, np.array([0.0, -1.0]))


def test_compute_perpendicular_is_orthogonal_to_input() -> None:
    """The result is orthogonal to the input vector for arbitrary inputs."""
    for vector in [np.array([2.0, 5.0]), np.array([-3.0, 1.0]), np.array([-1.0, -1.0])]:
        perp = compute_perpendicular(vector)
        assert np.abs(np.dot(perp, vector)) < 1e-9


def test_compute_perpendicular_degenerate_vector_returns_finite_default() -> None:
    """A near-zero vector doesn't divide by ~zero; returns a finite default."""
    perp = compute_perpendicular(np.array([1e-12, 1e-12]))
    assert np.isfinite(perp).all()


def test_compute_perpendicular_exact_zero_vector() -> None:
    """An exact zero vector also returns a finite default, not NaN."""
    perp = compute_perpendicular(np.array([0.0, 0.0]))
    assert np.isfinite(perp).all()


def test_compute_lane_boundaries_width_constant() -> None:
    """Distance between left and right boundary equals `width` everywhere."""
    centerline = np.array([[0.0, 0.0], [10.0, 0.0]])
    width = 12.0
    left, right = compute_lane_boundaries(centerline, width=width, lanes=2)

    for left_point, right_point in zip(left, right):
        dist = np.linalg.norm(left_point - right_point)
        assert np.abs(dist - width) < 0.1, f"Width mismatch: {dist} vs {width}"


def test_compute_lane_boundaries_offset_vector_is_perpendicular_at_endpoints() -> None:
    """At the first/last centerline point, only one adjacent segment
    exists, so the offset there is perpendicular to that single segment's
    direction unambiguously (the actually-correct property; see module
    docstring on the QOL checklist's own inverted test). Interior/bend
    points instead average both adjacent segment directions for a smooth
    turn -- see test_compute_lane_boundaries_smooth_through_bend -- so
    they are not checked against a single segment's direction here."""
    centerline = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 5.0]])
    left, _ = compute_lane_boundaries(centerline, width=10.0, lanes=2)

    first_dir = centerline[1] - centerline[0]
    first_dir = first_dir / np.linalg.norm(first_dir)
    first_offset = left[0] - centerline[0]
    first_offset_unit = first_offset / np.linalg.norm(first_offset)
    assert np.abs(np.dot(first_dir, first_offset_unit)) < 1e-6

    last_dir = centerline[-1] - centerline[-2]
    last_dir = last_dir / np.linalg.norm(last_dir)
    last_offset = left[-1] - centerline[-1]
    last_offset_unit = last_offset / np.linalg.norm(last_offset)
    assert np.abs(np.dot(last_dir, last_offset_unit)) < 1e-6


def test_compute_lane_boundaries_parallel_to_straight_centerline() -> None:
    """For a straight centerline, the boundary runs parallel to it."""
    centerline = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]])
    left, right = compute_lane_boundaries(centerline, width=10.0, lanes=2)

    c_dir = np.array([1.0, 0.0])
    for boundary in (left, right):
        for i in range(len(boundary) - 1):
            b_dir = boundary[i + 1] - boundary[i]
            b_dir = b_dir / np.linalg.norm(b_dir)
            assert np.abs(np.dot(c_dir, b_dir) - 1.0) < 1e-6


def test_compute_lane_boundaries_smooth_through_bend() -> None:
    """At an interior bend point, the boundary uses the averaged direction
    (no artificial kink), matching the shape of the centerline's own turn."""
    centerline = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]])
    left, right = compute_lane_boundaries(centerline, width=6.0, lanes=1)

    assert np.isfinite(left).all()
    assert np.isfinite(right).all()
    for left_point, right_point in zip(left, right):
        assert np.abs(np.linalg.norm(left_point - right_point) - 6.0) < 0.1


@pytest.mark.parametrize(
    "centerline,width,lanes",
    [
        (np.array([[0.0, 0.0]]), 10.0, 2),
        (np.array([[0.0, 0.0], [10.0, 0.0]]), 0.0, 2),
        (np.array([[0.0, 0.0], [10.0, 0.0]]), -5.0, 2),
        (np.array([[0.0, 0.0], [10.0, 0.0]]), 10.0, 0),
    ],
)
def test_compute_lane_boundaries_invalid_inputs_raise(centerline, width, lanes) -> None:
    """Degenerate inputs (too few points, non-positive width, zero lanes)
    raise ValueError rather than silently producing garbage geometry."""
    with pytest.raises(ValueError):
        compute_lane_boundaries(centerline, width=width, lanes=lanes)
