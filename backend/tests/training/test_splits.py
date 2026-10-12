from pathlib import Path

import pytest

from app.config import CameraConfig
from training.labels import LabelRow
from training.phash import video_phash
from training.splits import assert_no_demo_clips, source_groups, split_sources


def row(source_id: str, label: str = "normal", phash: str | None = None, file: str | None = None) -> LabelRow:
    return LabelRow(source_id=source_id, file=file or f"{source_id}.mp4", start=0.0, end=5.0, label=label,
                    origin="online", phash=phash or f"{abs(hash(source_id)) % (16 ** 12):012x}".rjust(48, "0"))


def test_source_groups_merges_near_duplicates():
    base = "0" * 48
    near = "0" * 47 + "3"  # 2 bits apart
    far = "f" * 48
    groups = source_groups([row("a", phash=base), row("b", phash=near), row("c", phash=far)])
    assert sorted(map(sorted, groups)) == [["a", "b"], ["c"]]


def test_split_sources_no_source_in_two_splits_and_groups_together():
    rows = []
    for i in range(12):
        rows.append(row(f"s{i}", "snatch", phash=f"{i:x}" * 48))
        rows.append(row(f"n{i}", "normal", phash=f"{(i + 1):x}" * 47 + f"{i:x}"))
    # make s0 and s1 near-duplicates
    rows[0] = row("s0", "snatch", phash="0" * 48)
    rows[2] = row("s1", "snatch", phash="0" * 47 + "1")
    mapping = split_sources(rows, seed=1)
    assert set(mapping) == {r.source_id for r in rows}
    assert mapping["s0"] == mapping["s1"]
    snatch_splits = {mapping[r.source_id] for r in rows if r.label == "snatch"}
    assert snatch_splits == {"train", "val", "test"}


def test_split_sources_is_deterministic():
    rows = [row(f"s{i}", "snatch", phash=f"{i:x}" * 48) for i in range(10)]
    assert split_sources(rows, seed=3) == split_sources(rows, seed=3)


def test_assert_no_demo_clips_by_name_and_phash(tmp_path: Path, make_video):
    data_dir = tmp_path / "data"
    demo = make_video(data_dir / "case-2.mp4", seconds=2.0, seed=11)
    cameras = [CameraConfig(id="C", name="n", location="l", clip="case-2.mp4")]
    ok = row("ok", phash=video_phash(make_video(tmp_path / "ok.mp4", seconds=2.0, seed=12)))
    assert_no_demo_clips([ok], cameras, data_dir)
    by_name = row("x", file="somewhere/case-2.mp4", phash=ok.phash)
    with pytest.raises(ValueError, match="case-2"):
        assert_no_demo_clips([by_name], cameras, data_dir)
    renamed = row("y", file="renamed.mp4", phash=video_phash(demo))
    with pytest.raises(ValueError, match="case-2"):
        assert_no_demo_clips([renamed], cameras, data_dir)
