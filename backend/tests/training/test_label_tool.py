from pathlib import Path

import pytest

from training.label_tool import LabelSession
from training.labels import read_labels


@pytest.fixture
def session(tmp_path: Path, make_video):
    root = tmp_path / "datasets"
    video = make_video(root / "staged" / "staged_a_01_snatch.mp4", seconds=4.0, seed=7)
    return LabelSession(video, tmp_path / "labels.csv", root)


def press(s: LabelSession, keys: str) -> None:
    for k in keys:
        s.handle_key(k)


def test_session_saves_snatch_row_from_markers(session: LabelSession, tmp_path: Path):
    press(session, ".....[")           # 5 frames at 10 fps = 0.5 s
    press(session, "ll")               # +2 s twice = 4.5 s, clamped to the last frame
    press(session, "j")                # back 2 s
    press(session, "]s")
    rows = read_labels(tmp_path / "labels.csv")
    assert len(rows) == 1
    r = rows[0]
    assert (r.label, r.origin, r.source_id) == ("snatch", "staged", "staged_staged_a_01_snatch")
    assert r.start == pytest.approx(0.5) and 1.5 < r.end < 2.5
    assert len(r.phash) == 48 and r.file == "staged/staged_a_01_snatch.mp4"


def test_session_refuses_conflicting_label_and_missing_markers(session: LabelSession,
                                                               tmp_path: Path):
    press(session, "s")                # no markers yet
    assert read_labels(tmp_path / "labels.csv") == []
    press(session, "[lll]s")           # 0 .. clamp: snatch over most of the video
    press(session, "j[.]n")            # a `normal` segment overlapping it
    labels = read_labels(tmp_path / "labels.csv")
    assert [r.label for r in labels] == ["snatch"]
    assert "overlap" in session.message


def test_session_quit_and_pause_keys(session: LabelSession):
    assert session.handle_key(" ") is True and session.paused is True
    assert session.handle_key("q") is False


def test_render_draws_a_bar_below_the_frame(session: LabelSession):
    frame = session.read_current()
    out = session.render(frame)
    assert out.shape[0] > frame.shape[0] and out.shape[2] == 3
