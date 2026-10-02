"""Unit tests for moving a YOLO dataset between machines."""

from pathlib import Path

import pytest

from src.evaluation.portable import (
    data_yaml,
    reroot_image_list,
    reroot_image_path,
    write_rerooted_lists,
)

ROOT = Path("/scratch/me/data/ds")


def test_windows_path_is_rerooted_from_its_images_folder() -> None:
    """Everything before the ``images`` folder is replaced, everything after is kept."""
    line = r"F:\datasets\bdd100k_control\images\100k\train\000f157f-30b30f5e.jpg"
    assert (
        reroot_image_path(line, ROOT)
        == "/scratch/me/data/ds/images/100k/train/000f157f-30b30f5e.jpg"
    )


def test_forward_slash_and_trailing_whitespace_work_too() -> None:
    """Paths from either OS style are handled, and stray whitespace is ignored."""
    assert reroot_image_path("F:/x/ds/images/live_0000_0_ego.png \n", ROOT) == (
        "/scratch/me/data/ds/images/live_0000_0_ego.png"
    )


def test_the_last_images_folder_is_the_dataset_one() -> None:
    """An ``images`` folder higher up the original path doesn't confuse the re-rooting."""
    line = r"F:\images\backups\ds\images\a.png"
    assert reroot_image_path(line, ROOT) == "/scratch/me/data/ds/images/a.png"


def test_a_path_without_an_images_folder_is_an_error() -> None:
    """A path that can't be re-rooted fails loudly instead of pointing at nothing."""
    with pytest.raises(ValueError, match="images"):
        reroot_image_path(r"F:\ds\pictures\a.png", ROOT)


def test_blank_lines_are_skipped() -> None:
    """Empty lines in a list file produce no entries."""
    assert reroot_image_list(["", r"F:\ds\images\a.png", "  "], ROOT) == [
        "/scratch/me/data/ds/images/a.png"
    ]


def test_write_rerooted_lists_writes_train_and_val(tmp_path: Path) -> None:
    """A dataset's train/val lists are re-rooted into one file each, named after the dataset."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "train.txt").write_text(
        "F:\\ds\\images\\a.png\nF:\\ds\\images\\b.png\n", encoding="utf-8"
    )
    (source / "val.txt").write_text("F:\\ds\\images\\c.png\n", encoding="utf-8")

    written = write_rerooted_lists(source, tmp_path / "newhome" / "ds", tmp_path / "out")

    train = written["train"].read_text(encoding="utf-8").splitlines()
    assert train == [
        (tmp_path / "newhome" / "ds" / "images" / "a.png").as_posix(),
        (tmp_path / "newhome" / "ds" / "images" / "b.png").as_posix(),
    ]
    assert written["train"].name == "ds_train.txt" and written["val"].name == "ds_val.txt"


def test_data_yaml_lists_every_train_file_and_the_four_classes() -> None:
    """A mixed dataset gets both train lists; classes keep the project's order."""
    text = data_yaml(
        [Path("/o/real_train.txt"), Path("/o/synth_train.txt")], Path("/o/real_val.txt")
    )
    assert "  - /o/real_train.txt\n  - /o/synth_train.txt\n" in text
    assert "val: /o/real_val.txt" in text
    assert "0: person" in text and "3: truck" in text
