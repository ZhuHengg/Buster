from pathlib import Path

import pytest
from pydantic import ValidationError

from training.labels import LabelRow, read_labels, validate_labels, write_labels


def row(**kw) -> LabelRow:
    base = dict(source_id="staged_a", file="staged/a.mp4", start=0.0, end=0.5, label="snatch",
                origin="staged", angle="high", light="day", phash="0" * 48)
    base.update(kw)
    return LabelRow(**base)


def test_label_row_rejects_end_before_start():
    with pytest.raises(ValidationError):
        row(start=1.0, end=1.0)
    with pytest.raises(ValidationError):
        row(start=2.0, end=1.0)


def test_labels_roundtrip_through_csv(tmp_path: Path):
    rows = [row(), row(label="normal", start=0.6, end=0.9, notes="a, b")]
    write_labels(tmp_path / "labels.csv", rows)
    assert read_labels(tmp_path / "labels.csv") == rows


def test_validate_flags_conflicting_overlap(tmp_path: Path, make_video):
    make_video(tmp_path / "staged" / "a.mp4", seconds=1.0)
    rows = [row(start=0.0, end=0.6, label="snatch"), row(start=0.4, end=0.9, label="normal")]
    errors = validate_labels(rows, tmp_path)
    assert len(errors) == 1 and "overlap" in errors[0]


def test_validate_allows_same_label_overlap_and_touching(tmp_path: Path, make_video):
    make_video(tmp_path / "staged" / "a.mp4", seconds=1.0)
    rows = [row(start=0.0, end=0.5), row(start=0.4, end=0.8),
            row(start=0.8, end=1.0, label="normal")]
    assert validate_labels(rows, tmp_path) == []


def test_validate_flags_end_beyond_duration(tmp_path: Path, make_video):
    make_video(tmp_path / "staged" / "a.mp4", seconds=1.0)
    errors = validate_labels([row(start=0.2, end=3.0)], tmp_path)
    assert len(errors) == 1 and "duration" in errors[0]


def test_validate_flags_unknown_file(tmp_path: Path):
    errors = validate_labels([row(file="staged/missing.mp4")], tmp_path)
    assert len(errors) == 1 and "missing" in errors[0]
