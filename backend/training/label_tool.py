"""OpenCV labelling tool: mark snatch / normal segments of one video into labels.csv.

    uv run python -m training.label_tool data/datasets/staged/staged_gateB_01_snatch.mp4

Keys: space pause/play | , . step one frame | j l jump -/+2 s | [ ] set segment start/end
      s save the segment as `snatch` | n save it as `normal` | q quit
The bar under the video shows saved segments (red = snatch, green = normal), the pending
marker range (yellow) and the playhead (white).
"""
import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from training.ingest import make_source_id, rel_path
from training.labels import (
    DATASETS_DIR, LABELS_PATH, LabelRow, read_labels, validate_labels, video_duration,
    write_labels,
)
from training.phash import video_phash

_ORIGIN_BY_FOLDER = {"ucf_crime": "ucf", "online": "online", "staged": "staged",
                     "feedback": "feedback"}
_BAR_H = 36
_SNATCH, _NORMAL, _PENDING, _HEAD = (60, 60, 230), (80, 190, 80), (0, 210, 240), (255, 255, 255)
_JUMP_S = 2.0
_MAX_W = 1100


class LabelSession:
    """Player state and key handling; `run()` is the thin OpenCV window around it."""

    def __init__(self, video: Path, labels_path: Path = LABELS_PATH, root: Path = DATASETS_DIR,
                 origin: str | None = None, angle: str | None = None, light: str | None = None):
        self.video = Path(video)
        self.labels_path = Path(labels_path)
        self.root = Path(root)
        self.rel = rel_path(self.video, self.root)
        self.cap = cv2.VideoCapture(str(self.video))
        if not self.cap.isOpened():
            raise FileNotFoundError(f"cannot open video: {self.video}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = video_duration(self.video)
        self.pos = 0
        self.paused = False
        self.start: float | None = None
        self.end: float | None = None
        self.message = ""
        known = [r for r in read_labels(self.labels_path) if r.file == self.rel]
        first = known[0] if known else None
        self.origin = origin or (first.origin if first else None) or _ORIGIN_BY_FOLDER.get(
            Path(self.rel).parts[0])
        if self.origin is None:
            raise ValueError("cannot infer origin from the folder; pass --origin")
        self.angle = angle or (first.angle if first else "unknown")
        self.light = light or (first.light if first else "unknown")
        self.phash = first.phash if first else video_phash(self.video)
        self.source_id = first.source_id if first else make_source_id(
            self.origin, self.video, self.phash)

    @property
    def time(self) -> float:
        return self.pos / self.fps

    def _seek(self, frame: int) -> None:
        self.pos = max(0, min(self.total - 1, frame))

    def handle_key(self, key: str) -> bool:
        """Returns False when the user quits."""
        if key == "q":
            return False
        if key == " ":
            self.paused = not self.paused
        elif key == ",":
            self.paused = True
            self._seek(self.pos - 1)
        elif key == ".":
            self.paused = True
            self._seek(self.pos + 1)
        elif key == "j":
            self._seek(self.pos - round(_JUMP_S * self.fps))
        elif key == "l":
            self._seek(self.pos + round(_JUMP_S * self.fps))
        elif key == "[":
            self.start = self.time
            self.message = f"start = {self.start:.2f}s"
        elif key == "]":
            self.end = self.time
            self.message = f"end = {self.end:.2f}s"
        elif key in ("s", "n"):
            self._save("snatch" if key == "s" else "normal")
        return True

    def _save(self, label: str) -> None:
        if self.start is None or self.end is None:
            self.message = "set start [ and end ] first"
            return
        try:
            row = LabelRow(source_id=self.source_id, file=self.rel, start=self.start, end=self.end,
                           label=label, origin=self.origin, angle=self.angle, light=self.light,
                           phash=self.phash)
        except ValueError:
            self.message = "end must be after start"
            return
        errors = validate_labels(self.segments() + [row], self.root)
        if errors:
            self.message = errors[0]
            return
        write_labels(self.labels_path, read_labels(self.labels_path) + [row])
        self.message = f"saved {label} {row.start:.2f}-{row.end:.2f}s"
        self.start = self.end = None

    def segments(self) -> list[LabelRow]:
        return [r for r in read_labels(self.labels_path) if r.file == self.rel]

    def read_current(self) -> np.ndarray:
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.pos)
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError(f"cannot read frame {self.pos} of {self.video}")
        return frame

    def render(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w > _MAX_W:
            frame = cv2.resize(frame, (_MAX_W, round(h * _MAX_W / w)))
            h, w = frame.shape[:2]
        bar = np.full((_BAR_H, w, 3), 30, np.uint8)

        def x(t: float) -> int:
            return min(w - 1, max(0, int(t / self.duration * w)))

        for r in self.segments():
            cv2.rectangle(bar, (x(r.start), 12), (x(r.end), _BAR_H - 4),
                          _SNATCH if r.label == "snatch" else _NORMAL, -1)
        if self.start is not None:
            cv2.rectangle(bar, (x(self.start), 4), (x(self.end if self.end else self.time), 10),
                          _PENDING, -1)
        cv2.line(bar, (x(self.time), 0), (x(self.time), _BAR_H), _HEAD, 2)
        out = np.vstack([frame, bar])
        text = (f"{self.time:6.2f} / {self.duration:.2f}s  frame {self.pos}  "
                f"{'PAUSED' if self.paused else 'playing'}  start={self.start}  end={self.end}")
        cv2.putText(out, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(out, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        if self.message:
            cv2.putText(out, self.message, (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(out, self.message, (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 220, 255), 1)
        return out

    def run(self) -> None:
        window = f"label: {self.rel}"
        delay = 1.0 / self.fps
        try:
            while True:
                tick = time.perf_counter()
                cv2.imshow(window, self.render(self.read_current()))
                wait_ms = max(1, int((delay - (time.perf_counter() - tick)) * 1000))
                code = cv2.waitKey(wait_ms if not self.paused else 30) & 0xFF
                if code != 0xFF and not self.handle_key(chr(code)):
                    break
                if not self.paused:
                    if self.pos >= self.total - 1:
                        self.paused = True
                    else:
                        self._seek(self.pos + 1)
        finally:
            self.cap.release()
            cv2.destroyAllWindows()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--origin", choices=["ucf", "online", "staged", "feedback"])
    ap.add_argument("--angle", choices=["high", "eye", "unknown"])
    ap.add_argument("--light", choices=["day", "dusk", "night", "unknown"])
    ap.add_argument("--labels", type=Path, default=LABELS_PATH)
    ap.add_argument("--root", type=Path, default=DATASETS_DIR)
    a = ap.parse_args()
    LabelSession(a.file, a.labels, a.root, a.origin, a.angle, a.light).run()


if __name__ == "__main__":
    main()
