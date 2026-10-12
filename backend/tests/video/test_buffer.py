import cv2
import numpy as np

from app.models import FrameDetections, Track
from app.video.buffer import FrameBuffer


def _det(pts: float, tracks: list[Track] | None = None, loop: int = 0) -> FrameDetections:
    return FrameDetections(camera_id="C", pts=pts, frame_w=200, frame_h=200, tracks=tracks or [], loop=loop)


def _person(id_: int, bbox=(50.0, 20.0, 150.0, 180.0)) -> Track:
    return Track(id=id_, cls="person", bbox=bbox, conf=0.9)


def _blank() -> np.ndarray:
    return np.full((200, 200, 3), 90, dtype=np.uint8)


def _lap_var(jpeg: bytes) -> float:
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def test_buffer_drops_frames_older_than_max_seconds():
    buf = FrameBuffer(max_seconds=2.0)
    for i in range(50):  # 5 s at 10 fps
        buf.push(i / 10, 0, _blank(), _det(i / 10))
    assert len(buf) <= 21
    assert buf.oldest_pts >= 4.9 - 2.0 - 1e-6


def test_keyframes_returns_n_jpegs_within_span():
    buf = FrameBuffer(max_seconds=10.0)
    for i in range(60):
        buf.push(i / 10, 0, _blank(), _det(i / 10, [_person(1)]))
    frames = buf.keyframes(center_pts=3.0, n=8, span=1.0)
    assert len(frames) == 8
    for jpeg in frames:
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        assert img.shape == (200, 200, 3)
    # clamped to buffer: center beyond the end still yields n frames
    assert len(buf.keyframes(center_pts=5.9, n=8, span=3.0)) == 8


def test_keyframes_draw_tracks_changes_pixels():
    buf = FrameBuffer()
    buf.push(0.0, 0, _blank(), _det(0.0, [_person(7)]))
    drawn = buf.keyframes(0.0, n=1, span=0.0, draw_tracks=True)[0]
    plain = buf.keyframes(0.0, n=1, span=0.0, draw_tracks=False)[0]
    assert drawn != plain


def test_best_snapshot_picks_sharpest():
    rng = np.random.default_rng(0)
    sharp = rng.integers(0, 255, (200, 200, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(sharp, (31, 31), 0)
    buf = FrameBuffer()
    buf.push(0.0, 0, blurred, _det(0.0, [_person(1)]))
    buf.push(0.1, 0, sharp, _det(0.1, [_person(1)]))
    buf.push(0.2, 0, blurred, _det(0.2, [_person(1)]))
    snap = buf.best_snapshot(1)
    assert snap is not None
    x1, y1, x2, y2 = 50, 20, 150, 180
    top = lambda img: img[y1 : y1 + int((y2 - y1) * 0.4), x1:x2]
    _, sharp_jpg = cv2.imencode(".jpg", top(sharp))
    _, blur_jpg = cv2.imencode(".jpg", top(blurred))
    v = _lap_var(snap)
    assert abs(v - _lap_var(sharp_jpg.tobytes())) < abs(v - _lap_var(blur_jpg.tobytes()))
    img = cv2.imdecode(np.frombuffer(snap, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == (64, 100)  # top 40% of a 160-high box, 100 wide


def test_best_snapshot_unknown_track_returns_none():
    buf = FrameBuffer()
    buf.push(0.0, 0, _blank(), _det(0.0, [_person(1)]))
    assert buf.best_snapshot(99) is None


def test_clear_empties_buffer():
    buf = FrameBuffer()
    buf.push(0.0, 0, _blank(), _det(0.0, [_person(1)]))
    buf.clear()
    assert len(buf) == 0
    assert buf.best_snapshot(1) is None


def test_keyframes_max_width_downscales_and_default_keeps_size():
    buf = FrameBuffer(max_seconds=10.0)
    wide = np.full((360, 1280, 3), 90, dtype=np.uint8)
    for i in range(10):
        buf.push(i / 10, 0, wide, _det(i / 10))
    small = cv2.imdecode(np.frombuffer(buf.keyframes(0.5, n=1, span=0.4, max_width=640)[0], np.uint8), cv2.IMREAD_COLOR)
    full = cv2.imdecode(np.frombuffer(buf.keyframes(0.5, n=1, span=0.4)[0], np.uint8), cv2.IMREAD_COLOR)
    assert small.shape[1] == 640 and small.shape[0] == 180
    assert full.shape[1] == 1280
