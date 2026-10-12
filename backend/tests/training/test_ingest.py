from pathlib import Path

from training.ingest import ingest_folder
from training.labels import read_labels
from training.phash import hamming


def test_ingest_adds_normal_rows_for_normal_folder(tmp_path: Path, make_video):
    root = tmp_path / "datasets"
    make_video(root / "ucf_crime" / "Normal_subset" / "n1.mp4", seconds=2.0, seed=1)
    make_video(root / "ucf_crime" / "Normal_subset" / "n2.mp4", seconds=3.0, seed=2)
    labels = tmp_path / "labels.csv"
    ingest_folder(root / "ucf_crime" / "Normal_subset", "ucf", labels, root)
    rows = read_labels(labels)
    assert {r.file for r in rows} == {"ucf_crime/Normal_subset/n1.mp4",
                                      "ucf_crime/Normal_subset/n2.mp4"}
    by_file = {r.file: r for r in rows}
    n2 = by_file["ucf_crime/Normal_subset/n2.mp4"]
    assert (n2.label, n2.origin, n2.start) == ("normal", "ucf", 0.0)
    assert abs(n2.end - 3.0) < 0.2
    assert n2.source_id == "ucf_n2" and len(n2.phash) == 48


def test_ingest_does_not_duplicate_existing_source(tmp_path: Path, make_video):
    root = tmp_path / "datasets"
    make_video(root / "online" / "normal" / "a.mp4", seconds=2.0, seed=3)
    labels = tmp_path / "labels.csv"
    ingest_folder(root / "online" / "normal", "online", labels, root)
    first = read_labels(labels)
    # same video again under another name: same content hash, so same source id
    make_video(root / "online" / "normal" / "a_copy.mp4", seconds=2.0, seed=3)
    ingest_folder(root / "online" / "normal", "online", labels, root)
    assert read_labels(labels) == first
    assert first[0].source_id.startswith("yt_")


def test_ingest_non_normal_folder_writes_no_rows_and_reports(tmp_path: Path, make_video, capsys):
    root = tmp_path / "datasets"
    make_video(root / "staged" / "staged_x_01_snatch.mp4", seconds=2.0, seed=4)
    labels = tmp_path / "labels.csv"
    ingest_folder(root / "staged", "staged", labels, root)
    assert not labels.exists() or read_labels(labels) == []
    assert "needs labelling" in capsys.readouterr().out


def test_phash_differs_for_different_videos_and_is_stable(tmp_path: Path, make_video):
    from training.phash import video_phash
    a = make_video(tmp_path / "a.mp4", seconds=2.0, seed=5)
    b = make_video(tmp_path / "b.mp4", seconds=2.0, seed=6)
    assert hamming(video_phash(a), video_phash(a)) == 0
    assert hamming(video_phash(a), video_phash(b)) > 6


def test_ingest_mixed_staged_folder_labels_normal_by_subfolder_or_filename(tmp_path: Path,
                                                                            make_video):
    root = tmp_path / "datasets"
    make_video(root / "staged" / "normal" / "staged_a_01.mp4", seconds=2.0, seed=10)
    make_video(root / "staged" / "staged_a_02_normal.mp4", seconds=2.0, seed=11)
    make_video(root / "staged" / "staged_a_03_snatch.mp4", seconds=2.0, seed=12)
    labels = tmp_path / "labels.csv"
    ingest_folder(root / "staged", "staged", labels, root)
    assert {r.file for r in read_labels(labels)} == {"staged/normal/staged_a_01.mp4",
                                                     "staged/staged_a_02_normal.mp4"}
