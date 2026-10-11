import numpy as np

from app.models import FrameDetections, Track

COCO_PERSON = 0
COCO_MOTORCYCLE = 3
_CLASS_NAMES = {COCO_PERSON: "person", COCO_MOTORCYCLE: "motorcycle"}


def _iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def attach_keypoints(
    tracks: list[Track],
    pose_boxes: list,
    pose_kpts: list,
    iou_min: float = 0.5,
) -> list[Track]:
    """Give each person track the keypoints of the pose box with the highest IoU >= iou_min."""
    out: list[Track] = []
    for tr in tracks:
        if tr.cls != "person":
            out.append(tr)
            continue
        best_i, best_iou = -1, iou_min
        for i, pb in enumerate(pose_boxes):
            score = _iou(tr.bbox, pb)
            if score >= best_iou:
                best_i, best_iou = i, score
        if best_i >= 0:
            kps = [(float(x), float(y), float(c)) for x, y, c in pose_kpts[best_i]]
            out.append(tr.model_copy(update={"keypoints": kps}))
        else:
            out.append(tr)
    return out


class Detector:
    """YOLO detect+track (ByteTrack) merged with YOLO pose. One instance per camera stream."""

    def __init__(
        self,
        det_model: str = "yolo11s.pt",
        pose_model: str = "yolo11s-pose.pt",
        device: str = "cuda:0",
        conf: float = 0.35,
    ):
        from ultralytics import YOLO

        self.device = device
        self.conf = conf
        self.det = YOLO(det_model)
        self.pose = YOLO(pose_model)

    def reset(self) -> None:
        predictor = getattr(self.det, "predictor", None)
        for tracker in getattr(predictor, "trackers", None) or []:
            tracker.reset()

    def process(self, frame: np.ndarray, camera_id: str, pts: float, loop: int) -> FrameDetections:
        h, w = frame.shape[:2]
        res = self.det.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[COCO_PERSON, COCO_MOTORCYCLE],
            conf=self.conf,
            device=self.device,
            verbose=False,
        )[0]
        tracks: list[Track] = []
        boxes = res.boxes
        if boxes is not None and boxes.id is not None:
            xyxy = boxes.xyxy.cpu().numpy()
            ids = boxes.id.int().cpu().numpy()
            confs = boxes.conf.cpu().numpy()
            clss = boxes.cls.int().cpu().numpy()
            for box, tid, c, k in zip(xyxy, ids, confs, clss):
                name = _CLASS_NAMES.get(int(k))
                if name is None:
                    continue
                tracks.append(
                    Track(id=int(tid), cls=name, bbox=tuple(float(v) for v in box), conf=float(c))
                )
        if any(t.cls == "person" for t in tracks):
            pres = self.pose(frame, conf=self.conf, device=self.device, verbose=False)[0]
            if pres.boxes is not None and pres.keypoints is not None and len(pres.boxes):
                tracks = attach_keypoints(
                    tracks,
                    [tuple(b) for b in pres.boxes.xyxy.cpu().numpy().tolist()],
                    pres.keypoints.data.cpu().numpy().tolist(),
                )
        return FrameDetections(
            camera_id=camera_id, pts=pts, frame_w=w, frame_h=h, tracks=tracks, loop=loop
        )
