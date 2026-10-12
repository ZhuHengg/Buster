import json
from pathlib import Path

import pytest

from app.trigger.gemini_screener import ScreenResult, ScreenUnavailable
from training.bench_screener import BenchmarkIncomplete, TooManyCalls, run, step_score
from training.labels import LabelRow, write_labels
from training.phash import video_phash


class FakeScreener:
    model = "fake-model"

    def __init__(self, suspicious=True):
        self.calls = 0
        self.suspicious = suspicious

    def screen(self, frames, camera):
        self.calls += 1
        assert len(frames) == 6 and all(f[:2] == b"\xff\xd8" for f in frames)  # JPEG bytes
        return ScreenResult(suspicious=self.suspicious, score=0.9, reason="x", suspect_track_ids=[])


@pytest.fixture
def dataset(tmp_path: Path, make_video):
    root = tmp_path / "datasets"
    rows = []
    for i in range(3):
        for label, seed in (("snatch", 20 + i), ("normal", 40 + i)):
            p = make_video(root / label / f"{label}{i}.mp4", seconds=8.0, seed=seed)
            start, end = (3.0, 5.0) if label == "snatch" else (0.0, 8.0)
            rows.append(LabelRow(source_id=f"{label}{i}", file=f"{label}/{label}{i}.mp4", start=start, end=end,
                                 label=label, origin="online", phash=video_phash(p)))
    labels = tmp_path / "labels.csv"
    write_labels(labels, rows)
    return {"labels": labels, "root": root, "tmp": tmp_path}


def kwargs(d, **kw):
    base = dict(labels=d["labels"], datasets_dir=d["root"], cameras=[], data_dir=d["tmp"] / "data",
                cache_path=d["tmp"] / "cache.jsonl", out_path=d["tmp"] / "report.json",
                threshold_path=d["tmp"] / "threshold.json", splits_path=d["tmp"] / "splits.json",
                stride_s=3.0, max_calls=1000)
    base.update(kw)
    return base


def test_bench_all_reports_metrics_and_calls_screener(dataset):
    screener = FakeScreener()
    report = run(split="all", screener=screener, **kwargs(dataset))
    assert screener.calls > 0
    assert report["events"] == 3 and report["event_recall"] == 1.0
    assert report["false_triggers"] >= 1  # the screener says yes on the normal videos too
    assert report["model"] == "fake-model" and report["calls"] == screener.calls
    assert json.loads((dataset["tmp"] / "report.json").read_text())["events"] == 3


def test_bench_refuses_over_max_calls_and_makes_no_calls(dataset):
    screener = FakeScreener()
    with pytest.raises(TooManyCalls):
        run(split="all", screener=screener, **kwargs(dataset, max_calls=2))
    assert screener.calls == 0


def test_bench_second_run_uses_cache_and_makes_no_calls(dataset):
    first = FakeScreener()
    run(split="all", screener=first, **kwargs(dataset))
    second = FakeScreener()
    report = run(split="all", screener=second, **kwargs(dataset, max_calls=0))
    assert second.calls == 0 and report["cache_hits"] == first.calls


def test_bench_val_writes_threshold_and_test_requires_it(dataset):
    with pytest.raises(FileNotFoundError):
        run(split="test", screener=FakeScreener(), **kwargs(dataset))
    run(split="val", screener=FakeScreener(), **kwargs(dataset))
    t = json.loads((dataset["tmp"] / "threshold.json").read_text())
    assert 0.0 <= t["threshold"] <= 1.01 and t["model"] == "fake-model"
    run(split="test", screener=FakeScreener(), **kwargs(dataset))


def test_bench_rejects_demo_clip_in_labels(dataset, make_video):
    from app.config import CameraConfig

    data_dir = dataset["tmp"] / "data"
    make_video(data_dir / "case-2.mp4", seconds=2.0, seed=99)
    cams = [CameraConfig(id="C", name="n", location="l", clip="case-2.mp4")]
    p = dataset["root"] / "snatch" / "case-2.mp4"
    make_video(p, seconds=2.0, seed=98)
    from training.labels import read_labels
    rows = read_labels(dataset["labels"]) + [LabelRow(source_id="demo", file="snatch/case-2.mp4", start=0.0,
                                                      end=1.0, label="snatch", origin="online",
                                                      phash=video_phash(p))]
    write_labels(dataset["labels"], rows)
    with pytest.raises(ValueError, match="case-2"):
        run(split="all", screener=FakeScreener(), **kwargs(dataset, cameras=cams))


class FlakyScreener(FakeScreener):
    def screen(self, frames, camera):
        n = self.calls
        self.calls += 1
        if n % 2:
            raise ScreenUnavailable("429")
        return ScreenResult(suspicious=True, score=0.9, reason="x", suspect_track_ids=[])


def test_step_score_non_suspicious_is_no_score():
    import math
    off = ScreenResult(suspicious=False, score=0.99, reason="x", suspect_track_ids=[])
    on = ScreenResult(suspicious=True, score=0.7, reason="x", suspect_track_ids=[])
    assert step_score(off) == -math.inf and step_score(on) == 0.7


def test_bench_errors_are_not_scored_and_val_refuses_to_save_a_threshold(dataset):
    with pytest.raises(BenchmarkIncomplete, match="failed"):
        run(split="val", screener=FlakyScreener(), **kwargs(dataset))
    assert not (dataset["tmp"] / "threshold.json").exists()
    assert json.loads((dataset["tmp"] / "report.json").read_text())["errors"] > 0  # report is still written


def test_bench_all_with_errors_reports_them(dataset):
    report = run(split="all", screener=FlakyScreener(), **kwargs(dataset))
    assert report["errors"] > 0


def test_bench_test_split_rejects_threshold_from_another_model_or_prompt(dataset):
    run(split="val", screener=FakeScreener(), **kwargs(dataset))
    other = FakeScreener()
    other.model = "another-model"
    with pytest.raises(ValueError, match="rerun --split val"):
        run(split="test", screener=other, **kwargs(dataset))


def test_bench_persists_splits_and_reuses_them(dataset):
    run(split="val", screener=FakeScreener(), **kwargs(dataset))
    saved = json.loads((dataset["tmp"] / "splits.json").read_text())
    assert set(saved.values()) <= {"train", "val", "test"} and len(saved) == 6
