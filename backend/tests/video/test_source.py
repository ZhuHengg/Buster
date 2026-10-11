import time

import pytest

from app.video.source import ClipSource


def test_source_reports_fps_and_size(tiny_clip):
    src = ClipSource(tiny_clip, realtime=False)
    assert src.fps == pytest.approx(10.0)
    assert src.size == (64, 48)
    assert src.duration == pytest.approx(1.0)


def test_source_loops_and_resets_pts(tiny_clip):
    it = iter(ClipSource(tiny_clip, realtime=False))
    out = [next(it) for _ in range(12)]
    first_loop = [(round(pts, 2), loop) for _, pts, loop in out[:10]]
    assert first_loop[0] == (0.0, 0)
    assert first_loop[-1] == (0.9, 0)
    _, pts, loop = out[10]
    assert loop == 1
    assert pts < 0.15
    assert out[11][1] > out[10][1]
    assert out[10][0].shape == (48, 64, 3)


def test_source_realtime_paces_frames(tiny_clip):
    it = iter(ClipSource(tiny_clip, realtime=True))
    t0 = time.perf_counter()
    for _ in range(6):
        next(it)
    assert time.perf_counter() - t0 >= 0.45  # 5 intervals of 0.1 s


def test_source_start_wall_time_updates_on_loop(tiny_clip):
    src = ClipSource(tiny_clip, realtime=False)
    it = iter(src)
    next(it)
    first = src.start_wall_time
    for _ in range(10):
        next(it)
    assert src.start_wall_time >= first
