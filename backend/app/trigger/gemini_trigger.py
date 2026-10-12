import logging
import math
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone

from app.config import CameraConfig, Settings
from app.models import CandidateEvent, FrameDetections
from app.trigger.gemini_screener import GeminiScreener, ScreenResult
from app.video.buffer import FrameBuffer

log = logging.getLogger(__name__)

WINDOW_S = 3.0
MAX_WIDTH = 640
ID_MEMORY_S = 4.0


class GeminiTrigger:
    """Step 1 trigger: asks Gemini whether the last ~3 s of frames show a snatch.

    Live mode runs each call on a worker thread and polls it from update(), so the video loop never
    waits. Blocking mode (offline precompute and benchmarks) calls inline because video time runs
    faster than wall time there. The pipeline pushes each frame to the shared buffer before update().
    """

    def __init__(
        self,
        settings: Settings,
        camera: CameraConfig,
        buffer: FrameBuffer,
        screener: GeminiScreener | None = None,
        blocking: bool = False,
        cooldown_s: float = 10.0,
        backoff_s: float = 30.0,
    ):
        self.settings, self.camera, self.buffer = settings, camera, buffer
        self.screener = screener or GeminiScreener(settings)
        self.blocking, self.cooldown_s, self.backoff_s = blocking, cooldown_s, backoff_s
        self._executor = None if blocking else ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemini-trigger")
        self._gen = 0
        self.reset()

    def reset(self) -> None:
        self._gen += 1  # in-flight results from before the reset are discarded
        self._inflight: tuple[Future, float, int] | None = None
        self._last_request_pts = -math.inf
        self._cooldown_until = -math.inf
        self._paused_until = -math.inf
        self._recent: deque[tuple[float, set[int]]] = deque()
        self._loop: int | None = None

    def update(self, fd: FrameDetections) -> CandidateEvent | None:
        if self._loop is not None and fd.loop != self._loop:
            self.reset()
        self._loop = fd.loop
        self._remember(fd)

        candidate = None
        if self._inflight is not None and self._inflight[0].done():
            future, request_pts, gen = self._inflight
            self._inflight = None
            candidate = self._handle(future, request_pts, gen, fd)
        if candidate is None and self._inflight is None and self._can_request(fd):
            candidate = self._request(fd)
        return candidate

    # -- internals -----------------------------------------------------------------------
    def _remember(self, fd: FrameDetections) -> None:
        self._recent.append((fd.pts, {t.id for t in fd.tracks}))
        while self._recent and fd.pts - self._recent[0][0] > ID_MEMORY_S:
            self._recent.popleft()

    def _can_request(self, fd: FrameDetections) -> bool:
        return (
            fd.pts >= self._cooldown_until
            and fd.pts >= self._paused_until
            and fd.pts - self._last_request_pts >= self.settings.screen_interval_s
            and any(t.cls == "person" for t in fd.tracks)
        )

    def _request(self, fd: FrameDetections) -> CandidateEvent | None:
        frames = self.buffer.keyframes(
            fd.pts, n=self.settings.screen_frames, span=WINDOW_S, max_width=MAX_WIDTH
        )
        if not frames:
            return None
        self._last_request_pts = fd.pts
        if self.blocking:
            future: Future = Future()
            try:
                future.set_result(self.screener.screen(frames, self.camera))
            except Exception as exc:  # noqa: BLE001 - any failure must back off, not crash the loop
                future.set_exception(exc)
            return self._handle(future, fd.pts, self._gen, fd)
        assert self._executor is not None
        self._inflight = (self._executor.submit(self.screener.screen, frames, self.camera), fd.pts, self._gen)
        return None

    def _handle(self, future: Future, request_pts: float, gen: int, fd: FrameDetections) -> CandidateEvent | None:
        try:
            result: ScreenResult = future.result()
        except Exception as exc:  # noqa: BLE001
            self._paused_until = fd.pts + self.backoff_s
            log.warning("Gemini screening failed for %s, pausing %gs: %s", self.camera.id, self.backoff_s, exc)
            return None
        s = self.settings
        if gen != self._gen or fd.pts - request_pts > s.screen_max_lag_s or fd.pts < self._cooldown_until:
            return None
        if not result.suspicious or result.score < s.screen_threshold:
            return None
        self._cooldown_until = fd.pts + self.cooldown_s
        known = {i for _, ids in self._recent for i in ids}
        return CandidateEvent(
            camera_id=fd.camera_id,
            pts=request_pts,
            loop=fd.loop,
            trigger="llm",
            suspect_track_ids=[i for i in result.suspect_track_ids if i in known],
            victim_track_id=result.victim_track_id if result.victim_track_id in known else None,
            motorcycle_track_id=result.motorcycle_track_id if result.motorcycle_track_id in known else None,
            detected_at=datetime.now(timezone.utc),
        )
