import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import CameraConfig
from app.incidents.store import IncidentStore
from app.models import CandidateEvent, Incident, IncidentStatus
from scripts.export_feedback import export_feedback
from training.labels import LabelRow, read_labels, write_labels
from training.phash import video_phash

S = IncidentStatus
NOW = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)


def incident(id_: str, status: S, clip: str, start: float = 1.0, end: float = 4.0) -> Incident:
    cand = CandidateEvent(camera_id="CAM-09", pts=start + 4, loop=0, trigger="rule", suspect_track_ids=[],
                          detected_at=NOW)
    return Incident(id=id_, camera_id="CAM-09", status=status, candidate=cand, clip_file=clip, clip_start=start,
                    clip_end=end, guard_decision_at=NOW, created_at=NOW)


class World:
    def __init__(self, tmp_path: Path, make_video):
        self.data = tmp_path / "data"
        self.datasets = self.data / "datasets"
        self.labels = self.data / "labels.csv"
        self.store = IncidentStore(self.data / "i.db")
        self.cameras = [CameraConfig(id="CAM-02", name="n", location="l", clip="case-2.mp4", analyse=True)]
        make_video(self.data / "case-2.mp4", seconds=6, seed=1)  # the demo clip
        make_video(self.data / "street.mp4", seconds=6, seed=2)  # a non-demo clip
        make_video(self.data / "street2.mp4", seconds=6, seed=3)

    def add(self, id_: str, status: S, clip: str = "street.mp4", **kw) -> Incident:
        inc = incident(id_, status, clip, **kw)
        self.store.save(inc)
        return inc

    def run(self, **kw):
        return export_feedback(self.store, self.cameras, self.data, self.labels, self.datasets, **kw)


@pytest.fixture
def world(tmp_path, make_video) -> World:
    return World(tmp_path, make_video)


def test_export_appends_guard_rejected_as_normal(world):
    world.add("INC-1", S.REJECTED)
    world.add("INC-2", S.APPROVED)  # approved incidents are not negatives
    world.add("INC-3", S.PENDING_REVIEW)
    result = world.run()
    (row,) = read_labels(world.labels)
    assert (row.label, row.origin, row.source_id) == ("normal", "feedback", "fb_INC-1")
    assert (row.start, row.end) == (1.0, 4.0)
    assert row.file == "feedback/fb_INC-1.mp4" and (world.datasets / row.file).exists()
    assert row.phash == video_phash(world.datasets / row.file)
    assert "guard rejected 2026-10-12" in row.notes
    assert len(result.appended) == 1


def test_export_idempotent(world):
    world.add("INC-1", S.REJECTED)
    world.run()
    first = world.labels.read_text(encoding="utf-8")
    again = world.run()
    assert again.appended == [] and again.skipped_existing == 1
    assert world.labels.read_text(encoding="utf-8") == first


def test_export_never_edits_existing_rows(world):
    existing = LabelRow(source_id="staged_a", file="staged/a.mp4", start=0, end=3, label="snatch",
                        origin="staged", phash="0" * 16)
    write_labels(world.labels, [existing])
    world.add("INC-1", S.REJECTED)
    world.run()
    rows = read_labels(world.labels)
    assert rows[0] == existing and [r.source_id for r in rows] == ["staged_a", "fb_INC-1"]


def test_export_skips_demo_clip_incidents(world, capsys):
    world.add("INC-1", S.REJECTED, clip="case-2.mp4")
    world.add("INC-2", S.REJECTED, clip="street.mp4")
    result = world.run()
    assert [r.source_id for r in read_labels(world.labels)] == ["fb_INC-2"]
    assert result.skipped_demo == 1
    assert "skipped 1 demo-clip incidents" in capsys.readouterr().out


def test_demo_clip_copy_under_another_name_is_still_refused(world, make_video):
    make_video(world.data / "renamed.mp4", seconds=6, seed=1)  # same pixels as case-2.mp4
    world.add("INC-1", S.REJECTED, clip="renamed.mp4")
    with pytest.raises(ValueError, match="demo clip"):
        world.run()
    assert not world.labels.exists() and not (world.datasets / "feedback").exists()  # nothing half-written


def test_ai_rejected_not_exported_without_flag(world):
    world.add("INC-1", S.AI_REJECTED)
    result = world.run()
    assert result.appended == [] and not world.labels.exists()


def test_include_ai_rejected_requires_a_confirmation_step(world):
    world.add("INC-1", S.AI_REJECTED)
    with pytest.raises(ValueError, match="confirm"):
        world.run(include_ai_rejected=True)  # never export an AI verdict unreviewed


def test_ai_rejected_exported_only_when_confirmed(world):
    for i in (1, 2, 3):
        world.add(f"INC-{i}", S.AI_REJECTED)
    answers = {"INC-1": "y", "INC-2": "n", "INC-3": "skip"}
    asked = []

    def confirm(inc: Incident, clip: Path) -> str:
        asked.append(inc.id)
        assert clip.exists()
        return answers[inc.id]

    result = world.run(include_ai_rejected=True, confirm=confirm)
    assert sorted(asked) == ["INC-1", "INC-2", "INC-3"]
    (row,) = read_labels(world.labels)
    assert row.source_id == "fb_INC-1" and row.label == "normal" and "AI rejected" in row.notes
    assert result.flagged_real == ["INC-2"]  # the human says a real snatch: needs hand labelling, not a negative


def test_guard_rejected_exported_directly_even_with_ai_flag(world):
    world.add("INC-1", S.REJECTED)
    result = world.run(include_ai_rejected=True, confirm=lambda inc, clip: pytest.fail("must not ask"))
    assert [r.source_id for r in result.appended] == ["fb_INC-1"]


def test_segment_is_clamped_to_the_video_and_unusable_ones_skipped(world):
    world.add("INC-1", S.REJECTED, start=4.0, end=9.0)  # video is 6 s long
    world.add("INC-2", S.REJECTED, clip="street2.mp4", start=7.0, end=9.0)  # entirely past the end
    result = world.run()
    (row,) = read_labels(world.labels)
    assert (row.source_id, row.end) == ("fb_INC-1", pytest.approx(6.0, abs=0.2))
    assert result.skipped_unusable == 1


def test_missing_clip_is_skipped_not_fatal(world):
    world.add("INC-1", S.REJECTED, clip="gone.mp4")
    result = world.run()
    assert result.appended == [] and result.skipped_unusable == 1
