import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import CameraConfig, Settings
from app.incidents.service import IncidentService
from app.models import (
    CandidateEvent,
    FrameDetections,
    Incident,
    VerificationResult,
)
from app.trigger.base import Trigger
from app.trigger.direction import escape_direction
from app.verify.base import Verifier
from app.video.buffer import FrameBuffer
from app.video.source import ClipSource

log = logging.getLogger(__name__)

UNAVAILABLE = "AI verification unavailable"


def detections_msg(fd: FrameDetections, suspects: set[int]) -> dict:
    return {
        "type": "detections",
        "camera_id": fd.camera_id,
        "loop": fd.loop,
        "pts": fd.pts,
        "frame_w": fd.frame_w,
        "frame_h": fd.frame_h,
        "tracks": [
            {"id": t.id, "cls": t.cls, "bbox": list(t.bbox), "suspect": t.id in suspects} for t in fd.tracks
        ],
    }


def sync_msg(camera_id: str, loop: int, pts: float) -> dict:
    return {"type": "camera.sync", "camera_id": camera_id, "loop": loop, "pts": pts, "wall_time": time.time()}


def _suspect_ids(candidate: CandidateEvent) -> set[int]:
    ids = set(candidate.suspect_track_ids)
    if candidate.motorcycle_track_id is not None:
        ids.add(candidate.motorcycle_track_id)
    return ids


class _TaskSet:
    """Keeps background tasks alive and lets the owner wait for them."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


class CameraPipeline:
    """clip source -> detector -> buffer -> detections broadcast -> trigger -> incident -> verification."""

    def __init__(
        self,
        camera: CameraConfig,
        settings: Settings,
        detector: Any,
        trigger: Trigger,
        verifier: Verifier,
        service: IncidentService,
        hub: Any,
        buffer: FrameBuffer,
        source: Any = None,
    ):
        self.camera, self.settings = camera, settings
        self.detector, self.trigger, self.verifier = detector, trigger, verifier
        self.service, self.hub, self.buffer = service, hub, buffer
        self.source = source
        self._recent: deque[FrameDetections] = deque(maxlen=200)
        self._suspects: set[int] = set()
        self._tasks = _TaskSet()
        self._last_analysed_pts: float | None = None
        self._last_fd: FrameDetections | None = None

    def _due(self, pts: float) -> bool:
        """True when this frame should be analysed: at most `analyse_fps` per second of clip time."""
        fps = self.settings.analyse_fps
        if not fps or self._last_analysed_pts is None:
            return True
        return pts - self._last_analysed_pts >= 1.0 / fps - 1e-6

    async def run(self) -> None:
        source = self.source
        if source is None:
            source = ClipSource(self.settings.data_dir / (self.camera.clip or ""), realtime=True)
        it = iter(source)
        last_loop: int | None = None
        last_sync_sec: int | None = None
        try:
            while True:
                item = await asyncio.to_thread(next, it, None)
                if item is None:
                    break
                frame, pts, loop = item
                if last_loop is not None and loop != last_loop:
                    self._reset()
                    last_sync_sec = None
                last_loop = loop

                if not self._due(pts) and self._last_fd is not None:
                    # skipped: buffered with the last boxes so keyframes stay smooth, but not analysed
                    self.buffer.push(pts, loop, frame, self._last_fd.model_copy(update={"pts": pts}))
                    continue
                fd = await asyncio.to_thread(self.detector.process, frame, self.camera.id, pts, loop)
                self._last_analysed_pts, self._last_fd = pts, fd
                self.buffer.push(pts, loop, frame, fd)
                self._recent.append(fd)
                await self.hub.broadcast(detections_msg(fd, self._suspects))
                if last_sync_sec != int(pts):
                    last_sync_sec = int(pts)
                    await self.hub.broadcast(sync_msg(self.camera.id, loop, pts))

                candidate = self.trigger.update(fd)
                if candidate is not None:
                    try:
                        await self._on_candidate(candidate)
                    except Exception:
                        log.exception("failed to open incident for %s", self.camera.id)
        finally:
            await self._tasks.wait_idle()

    def _reset(self) -> None:
        self.detector.reset()
        self.trigger.reset()
        self.buffer.clear()
        self._recent.clear()
        self._suspects.clear()  # track IDs restart with the loop
        self._last_analysed_pts = self._last_fd = None  # pts restarts at 0

    async def _on_candidate(self, candidate: CandidateEvent) -> None:
        keyframes = self.buffer.keyframes(candidate.pts, n=8, span=3.0)
        snapshots: dict[int, bytes] = {}
        for track_id in candidate.suspect_track_ids:
            snap = self.buffer.best_snapshot(track_id)
            if snap is not None:
                snapshots[track_id] = snap
        direction: tuple[str | None, str | None] = (None, None)
        if candidate.motorcycle_track_id is not None:
            direction = escape_direction(list(self._recent), candidate.motorcycle_track_id, self.camera)
        self._suspects |= _suspect_ids(candidate)
        incident = await self.service.open(candidate, self.camera, self.camera.clip or "", snapshots)
        self._tasks.spawn(self._verify(incident, candidate, keyframes, direction))

    async def _verify(
        self,
        incident: Incident,
        candidate: CandidateEvent,
        keyframes: list[bytes],
        direction: tuple[str | None, str | None],
    ) -> None:
        result: VerificationResult | None = None
        error: str | None = None
        try:
            result = await self.verifier.verify(candidate, keyframes, self.camera)
        except Exception as exc:  # any failure must still reach the guard as an unverified alert
            log.warning("verification failed for %s: %s", incident.id, exc)
            error = f"{UNAVAILABLE}: {exc}"
        await self.service.attach_verification(incident.id, result, error, direction)


class ReplayPipeline:
    """Plays precomputed pipeline output with the same messages and timing as the live pipeline."""

    def __init__(
        self,
        camera: CameraConfig,
        precomputed_path: Path,
        service: IncidentService,
        hub: Any,
        realtime: bool = True,
        max_loops: int | None = None,
        verify_delay: float = 2.0,
    ):
        self.camera, self.path = camera, Path(precomputed_path)
        self.service, self.hub = service, hub
        self.realtime, self.max_loops, self.verify_delay = realtime, max_loops, verify_delay
        self._tasks = _TaskSet()

    async def run(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        frames = [FrameDetections.model_validate(f) for f in data["frames"]]
        candidates = sorted(data.get("candidates", []), key=lambda c: c["candidate"]["pts"])
        if not frames:
            return
        fps = data.get("fps") or 25.0
        loop_len = frames[-1].pts + 1.0 / fps
        loop = 0
        try:
            while self.max_loops is None or loop < self.max_loops:
                suspects: set[int] = set()
                pending = list(candidates)
                last_sec: int | None = None
                started = time.perf_counter()
                for fd in frames:
                    fd = fd.model_copy(update={"loop": loop})
                    if self.realtime:
                        delay = started + fd.pts - time.perf_counter()
                        if delay > 0:
                            await asyncio.sleep(delay)
                    await self.hub.broadcast(detections_msg(fd, suspects))
                    if last_sec != int(fd.pts):
                        last_sec = int(fd.pts)
                        await self.hub.broadcast(sync_msg(self.camera.id, loop, fd.pts))
                    while pending and pending[0]["candidate"]["pts"] <= fd.pts:
                        entry = pending.pop(0)
                        suspects |= await self._inject(entry, loop)
                if self.realtime:
                    delay = started + loop_len - time.perf_counter()
                    if delay > 0:
                        await asyncio.sleep(delay)
                loop += 1
        finally:
            await self._tasks.wait_idle()

    async def _inject(self, entry: dict, loop: int) -> set[int]:
        candidate = CandidateEvent.model_validate(entry["candidate"]).model_copy(
            update={"detected_at": datetime.now(timezone.utc), "loop": loop}
        )
        snapshots: dict[int, bytes] = {}
        for track_id in candidate.suspect_track_ids:
            snap = self.path.parent / f"{self.camera.id}_{track_id}.jpg"
            if snap.exists():
                snapshots[track_id] = snap.read_bytes()
        incident = await self.service.open(candidate, self.camera, self.camera.clip or "", snapshots)
        verification = entry.get("verification")
        result = VerificationResult.model_validate(verification) if verification else None
        direction = tuple(entry.get("direction") or (None, None))
        self._tasks.spawn(self._attach(incident, result, direction))
        return _suspect_ids(candidate)

    async def _attach(
        self, incident: Incident, result: VerificationResult | None, direction: tuple[str | None, str | None]
    ) -> None:
        if self.verify_delay:
            await asyncio.sleep(self.verify_delay)
        await self.service.attach_verification(
            incident.id, result, None if result else UNAVAILABLE, direction
        )
