"""Unit tests for moving a YOLO dataset between machines."""

from pathlib import Path

import pytest

from src.evaluation.portable import (
    class_counts,
    data_yaml,
    missing_files,
    reroot_image_list,
    reroot_image_path,
    write_class_free_list,
    write_fraction_list,
    write_random_list,
    write_ranked_list,
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


def test_fraction_list_takes_the_first_lines_and_nests(tmp_path: Path) -> None:
    """25% is the first quarter of the list and is contained in the 50% list."""
    source = tmp_path / "train.txt"
    source.write_text("".join(f"/d/images/{i}.jpg\n" for i in range(8)), encoding="utf-8")

    quarter = write_fraction_list(source, 0.25, tmp_path / "q.txt").read_text().split()
    half = write_fraction_list(source, 0.5, tmp_path / "h.txt").read_text().split()

    assert quarter == ["/d/images/0.jpg", "/d/images/1.jpg"]
    assert half[:2] == quarter and len(half) == 4


def test_missing_files_reports_absent_images_and_labels(tmp_path: Path) -> None:
    """An image needs both itself and its label file; an empty label file is fine."""
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir()
    labels.mkdir()
    (images / "ok.jpg").write_bytes(b"x")
    (labels / "ok.txt").write_text("", encoding="utf-8")
    (images / "nolabel.jpg").write_bytes(b"x")
    listing = tmp_path / "list.txt"
    listing.write_text(
        "\n".join(str(images / name) for name in ("ok.jpg", "nolabel.jpg", "gone.jpg")),
        encoding="utf-8",
    )

    problems = missing_files(listing)

    assert len(problems) == 2
    assert any("label missing" in p and "nolabel" in p for p in problems)
    assert any("image missing" in p and "gone" in p for p in problems)


def test_class_free_and_random_lists(tmp_path: Path) -> None:
    """Images with a listed class are dropped; the random list is reproducible and sized."""
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir()
    labels.mkdir()
    rows = {
        "a": "0 0.5 0.5 0.1 0.1\n1 0.5 0.5 0.1 0.1",
        "b": "3 0.5 0.5 0.1 0.1",
        "c": "",
        "d": "2 0.5 0.5 0.1 0.1",
    }
    for name, text in rows.items():
        (images / f"{name}.jpg").write_bytes(b"x")
        (labels / f"{name}.txt").write_text(text, encoding="utf-8")
    listing = tmp_path / "list.txt"
    listing.write_text("\n".join(str(images / f"{n}.jpg") for n in rows) + "\n", encoding="utf-8")

    kept = write_class_free_list([listing], {2, 3}, tmp_path / "free.txt").read_text().split()
    first = write_random_list([listing], 2, 0, tmp_path / "r1.txt").read_text().split()
    again = write_random_list([listing], 2, 0, tmp_path / "r2.txt").read_text().split()

    assert [Path(x).stem for x in kept] == ["a", "c"]
    assert first == again and len(first) == 2


def test_ranked_list_picks_the_most_or_fewest_boxes_of_the_weighted_classes(tmp_path: Path) -> None:
    """Weighted counts rank the images; ``highest`` flips the direction; rows are counted."""
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir()
    labels.mkdir()
    rows = {
        "a": "0 .5 .5 .1 .1\n0 .5 .5 .1 .1\n3 .5 .5 .1 .1",
        "b": "0 .5 .5 .1 .1",
        "c": "1 .5 .5 .1 .1",
    }
    for name, text in rows.items():
        (images / f"{name}.jpg").write_bytes(b"x")
        (labels / f"{name}.txt").write_text(text, encoding="utf-8")
    listing = tmp_path / "list.txt"
    listing.write_text("\n".join(str(images / f"{n}.jpg") for n in rows) + "\n", encoding="utf-8")

    assert class_counts(str(images / "a.jpg")) == {0: 2, 3: 1}
    top = (
        write_ranked_list([listing], {0: 1.0, 3: 1.0}, 2, tmp_path / "top.txt").read_text().split()
    )
    low = (
        write_ranked_list([listing], {0: 1.0, 3: 1.0}, 2, tmp_path / "low.txt", False)
        .read_text()
        .split()
    )
    assert [Path(x).stem for x in top] == ["a", "b"]
    assert [Path(x).stem for x in low] == ["c", "b"]
