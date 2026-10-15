import time
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np


class ClipSource:
    """Endless looping iterator over a clip: yields (frame, pts, loop).

    pts restarts at 0 on every loop and `loop` increments. With realtime=True frames are
    paced at the clip's fps so the stream behaves like a live camera.
    """

    def __init__(self, path: Path, realtime: bool = True):
        self.path = Path(path)
        self.realtime = realtime
        cap = cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            raise FileNotFoundError(f"cannot open clip: {self.path}")
        self.fps: float = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.size: tuple[int, int] = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        self.duration: float = cap.get(cv2.CAP_PROP_FRAME_COUNT) / self.fps
        cap.release()
        self.start_wall_time: float = time.time()
        self._loop_start: float = time.perf_counter()

    def delay(self, seconds: float) -> None:
        """Push the playback clock back (the clip was paused): the next frame follows the last one
        instead of skipping ahead to catch up with the wall clock."""
        self._loop_start += seconds
        self.start_wall_time += seconds

    def __iter__(self) -> Iterator[tuple[np.ndarray, float, int]]:
        cap = cv2.VideoCapture(str(self.path))
        loop = 0
        index = 0
        self.start_wall_time = time.time()
        self._loop_start = time.perf_counter()
        try:
            while True:
                if self.realtime:
                    # a slow consumer must not fall behind the wall clock: skip stale frames
                    behind = int((time.perf_counter() - (self._loop_start + index / self.fps)) * self.fps)
                    for _ in range(behind):
                        if not cap.grab():
                            break
                        index += 1
                ok, frame = cap.read()
                if not ok:
                    if index == 0:
                        raise RuntimeError(f"clip has no readable frames: {self.path}")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    loop += 1
                    index = 0
                    self.start_wall_time = time.time()
                    self._loop_start = time.perf_counter()
                    continue
                pts = index / self.fps
                if self.realtime:
                    delay = self._loop_start + pts - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                yield frame, pts, loop
                index += 1
        finally:
            cap.release()
