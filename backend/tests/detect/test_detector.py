from pathlib import Path

import pytest

from app.detect.detector import Detector, attach_keypoints
from app.models import Track

DATA = Path(__file__).resolve().parents[2] / "data"


def _kp(seed: float) -> list[tuple[float, float, float]]:
    return [(seed, seed, 0.9)] * 17


def _person(id_: int, bbox) -> Track:
    return Track(id=id_, cls="person", bbox=bbox, conf=0.9)


def test_attach_keypoints_matches_best_iou():
    tracks = [_person(1, (0, 0, 100, 200)), _person(2, (300, 0, 400, 200))]
    pose_boxes = [(298, 2, 401, 199), (2, 1, 99, 198)]
    pose_kpts = [_kp(2.0), _kp(1.0)]
    out = attach_keypoints(tracks, pose_boxes, pose_kpts)
    assert out[0].keypoints == _kp(1.0)
    assert out[1].keypoints == _kp(2.0)


def test_attach_keypoints_ignores_low_iou():
    tracks = [_person(1, (0, 0, 100, 200))]
    out = attach_keypoints(tracks, [(90, 0, 300, 200)], [_kp(1.0)], iou_min=0.5)
    assert out[0].keypoints is None


def test_attach_keypoints_skips_motorcycles():
    moto = Track(id=5, cls="motorcycle", bbox=(0, 0, 100, 200), conf=0.8)
    out = attach_keypoints([moto], [(0, 0, 100, 200)], [_kp(1.0)])
    assert out[0].keypoints is None
    assert out[0].cls == "motorcycle"


@pytest.mark.gpu
def test_process_on_real_clip_finds_person():
    import cv2
    import torch

    clip = DATA / "case-1.mp4"
    if not torch.cuda.is_available() or not clip.exists():
        pytest.skip("needs CUDA and data/case-1.mp4")
    det = Detector()
    cap = cv2.VideoCapture(str(clip))
    persons = 0
    for i in range(30):
        ok, frame = cap.read()
        assert ok
        fd = det.process(frame, "CAM-07", i / 30.0, 0)
        assert fd.frame_w == frame.shape[1] and fd.frame_h == frame.shape[0]
        persons += sum(t.cls == "person" for t in fd.tracks)
    cap.release()
    assert persons >= 1
