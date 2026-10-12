from collections import deque

import cv2
import numpy as np

from app.models import FrameDetections

SUSPECT_COLOUR = (0, 0, 255)
BOX_COLOUR = (255, 255, 255)


def _jpeg(img: np.ndarray, quality: int = 85, max_width: int | None = None) -> bytes:
    if max_width is not None and img.shape[1] > max_width:
        scale = max_width / img.shape[1]
        img = cv2.resize(img, (max_width, max(1, round(img.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return buf.tobytes()


class FrameBuffer:
    """Ring buffer of recent frames with their detections."""

    def __init__(self, max_seconds: float = 10.0):
        self.max_seconds = max_seconds
        self._items: deque[tuple[float, int, np.ndarray, FrameDetections]] = deque()

    def __len__(self) -> int:
        return len(self._items)

    @property
    def oldest_pts(self) -> float:
        return self._items[0][0]

    def push(self, pts: float, loop: int, frame: np.ndarray, detections: FrameDetections) -> None:
        self._items.append((pts, loop, frame, detections))
        while self._items and pts - self._items[0][0] > self.max_seconds:
            self._items.popleft()

    def clear(self) -> None:
        self._items.clear()

    def keyframes(
        self,
        center_pts: float,
        n: int = 8,
        span: float = 3.0,
        draw_tracks: bool = True,
        max_width: int | None = None,
    ) -> list[bytes]:
        if not self._items:
            return []
        oldest, newest = self._items[0][0], self._items[-1][0]
        center = min(max(center_pts, oldest), newest)
        lo, hi = max(center - span, oldest), min(center + span, newest)
        out: list[bytes] = []
        for t in np.linspace(lo, hi, n):
            _, _, frame, det = min(self._items, key=lambda item: abs(item[0] - t))
            img = frame.copy()
            if draw_tracks:
                self._draw(img, det)
            out.append(_jpeg(img, max_width=max_width))
        return out

    @staticmethod
    def _draw(img: np.ndarray, det: FrameDetections) -> None:
        for tr in det.tracks:
            x1, y1, x2, y2 = (int(v) for v in tr.bbox)
            colour = SUSPECT_COLOUR if tr.cls == "motorcycle" else BOX_COLOUR
            cv2.rectangle(img, (x1, y1), (x2, y2), colour, 2)
            cv2.putText(
                img, f"#{tr.id}", (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2
            )

    def best_snapshot(self, track_id: int) -> bytes | None:
        """JPEG of the top 40% of the track's bbox from the sharpest buffered frame."""
        best_crop, best_score = None, -1.0
        for _, _, frame, det in self._items:
            for tr in det.tracks:
                if tr.id != track_id:
                    continue
                x1, y1, x2, y2 = tr.bbox
                h, w = frame.shape[:2]
                top = int(max(0, y1))
                bottom = int(min(h, y1 + (y2 - y1) * 0.4))
                left, right = int(max(0, x1)), int(min(w, x2))
                if bottom <= top or right <= left:
                    continue
                crop = frame[top:bottom, left:right]
                score = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
                if score > best_score:
                    best_crop, best_score = crop, score
        return None if best_crop is None else _jpeg(best_crop)
