import threading
import time

import numpy as np

from app.config import CameraConfig, Settings
from app.incidents.service import IncidentService
from app.incidents.store import IncidentStore
from app.models import IncidentStatus
from app.pipeline import CameraPipeline
from app.trigger.gemini_screener import ScreenResult, ScreenUnavailable
from app.trigger.gemini_trigger import GeminiTrigger
from app.verify.mock_verifier import MockVerifier
from app.video.buffer import FrameBuffer
from tests.test_pipeline import FakeDetector, FakeHub, make_source
from tests.trigger.conftest import Ent, make_scene

CAMERA = CameraConfig(id="CAM-07", name="Row B", location="Jalan Limau Manis")
YES = ScreenResult(suspicious=True, score=0.9, reason="grab", suspect_track_ids=[2], motorcycle_track_id=3,
                   victim_track_id=1)
NO = ScreenResult(suspicious=False, score=0.1, reason="nothing", suspect_track_ids=[])


class FakeScreener:
    def __init__(self, result=YES, delay: float = 0.0, error: Exception | None = None):
        self.result, self.delay, self.error = result, delay, error
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def screen(self, frames, camera):
        with self._lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.error:
                raise self.error
            return self.result
        finally:
            with self._lock:
                self.active -= 1


def settings(**kw) -> Settings:
    kw.setdefault("screen_interval_s", 1.0)
    return Settings(_env_file=None, gemini_api_key="k", **kw)


def scene(t_end=3.0, loop=0, t_start=0.0, with_person=True, ids=(1, 2, 3)):
    ents = []
    if with_person:
        ents = [Ent(i, "person", lambda t: (500.0, 400.0), (60.0, 160.0)) for i in ids]
    return make_scene(ents, t_end, loop=loop, t_start=t_start)


def feed(trig, buf, frames):
    """Push each frame to the buffer, then update the trigger. Returns the candidates in order."""
    out = []
    for fd in frames:
        buf.push(fd.pts, fd.loop, np.full((90, 160, 3), 90, np.uint8), fd)
        c = trig.update(fd)
        if c is not None:
            out.append(c)
    return out


def make(screener, blocking=True, **kw):
    buf = FrameBuffer()
    return GeminiTrigger(settings(**kw), CAMERA, buf, screener=screener, blocking=blocking), buf


def test_fires_when_screen_positive_blocking():
    trig, buf = make(FakeScreener())
    cands = feed(trig, buf, scene())
    assert len(cands) == 1
    c = cands[0]
    assert c.trigger == "llm" and c.camera_id == "CAM-07"
    assert c.suspect_track_ids == [2] and c.victim_track_id == 1 and c.motorcycle_track_id == 3


def test_below_threshold_does_not_fire():
    low = ScreenResult(suspicious=True, score=0.3, reason="meh", suspect_track_ids=[])
    trig, buf = make(FakeScreener(result=low), screen_threshold=0.5)
    assert feed(trig, buf, scene()) == []


def test_not_suspicious_does_not_fire():
    trig, buf = make(FakeScreener(result=NO))
    assert feed(trig, buf, scene()) == []


def test_no_person_means_no_call():
    screener = FakeScreener()
    trig, buf = make(screener)
    assert feed(trig, buf, scene(with_person=False)) == []
    assert screener.calls == 0


def test_respects_interval_in_blocking_mode():
    screener = FakeScreener(result=NO)
    trig, buf = make(screener, screen_interval_s=1.0)
    feed(trig, buf, scene(t_end=3.5))
    assert screener.calls == 4  # pts 0, 1, 2, 3


def test_live_update_never_blocks_and_single_inflight():
    screener = FakeScreener(result=NO, delay=0.4)
    trig, buf = make(screener, blocking=False, screen_interval_s=0.5)
    worst = 0.0
    for fd in scene(t_end=3.0):
        buf.push(fd.pts, fd.loop, np.full((90, 160, 3), 90, np.uint8), fd)
        t0 = time.perf_counter()
        trig.update(fd)
        worst = max(worst, time.perf_counter() - t0)
    assert worst < 0.05
    assert screener.max_active == 1
    assert screener.calls == 1  # frames were fed faster than the first call finished


def test_live_positive_result_fires_on_a_later_frame():
    trig, buf = make(FakeScreener(delay=0.1), blocking=False)
    frames = scene(t_end=1.0)
    assert feed(trig, buf, frames[:2]) == []
    time.sleep(0.3)
    later = feed(trig, buf, frames[2:4])
    assert len(later) == 1 and later[0].pts == 0.0  # candidate pts is the screened window's end


def test_stale_result_discarded_when_lagging():
    trig, buf = make(FakeScreener(delay=0.1), blocking=False, screen_max_lag_s=0.5)
    feed(trig, buf, scene(t_end=0.2)[:1])
    time.sleep(0.3)
    late = scene(t_start=5.0, t_end=5.2)
    assert feed(trig, buf, late[:1]) == []


def test_result_from_previous_loop_discarded_after_reset():
    trig, buf = make(FakeScreener(delay=0.1), blocking=False)
    feed(trig, buf, scene(t_end=0.2)[:1])
    trig.reset()
    buf.clear()
    time.sleep(0.3)
    assert feed(trig, buf, scene(t_end=0.1, loop=1)) == []


def test_loop_change_discards_inflight_result():
    trig, buf = make(FakeScreener(delay=0.1), blocking=False)
    feed(trig, buf, scene(t_end=0.2)[:1])
    time.sleep(0.3)
    assert feed(trig, buf, scene(t_end=0.1, loop=1)) == []


def test_unavailable_pauses_then_retries():
    screener = FakeScreener(error=ScreenUnavailable("429"))
    trig, buf = make(screener, screen_interval_s=1.0)
    trig.backoff_s = 5.0
    assert feed(trig, buf, scene(t_end=4.0)) == []
    assert screener.calls == 1  # no calls while paused
    feed(trig, buf, scene(t_start=5.0, t_end=6.0))
    assert screener.calls == 2


def test_unexpected_exception_does_not_propagate():
    trig, buf = make(FakeScreener(error=RuntimeError("bug")))
    assert feed(trig, buf, scene(t_end=1.0)) == []


def test_candidate_without_track_ids_is_valid():
    bare = ScreenResult(suspicious=True, score=0.9, reason="grab", suspect_track_ids=[])
    trig, buf = make(FakeScreener(result=bare))
    c = feed(trig, buf, scene())[0]
    assert c.suspect_track_ids == [] and c.motorcycle_track_id is None and c.victim_track_id is None


def test_hallucinated_track_ids_are_dropped():
    ghost = ScreenResult(suspicious=True, score=0.9, reason="grab", suspect_track_ids=[2, 99],
                         motorcycle_track_id=98, victim_track_id=1)
    trig, buf = make(FakeScreener(result=ghost))
    c = feed(trig, buf, scene(ids=(1, 2)))[0]
    assert c.suspect_track_ids == [2] and c.motorcycle_track_id is None and c.victim_track_id == 1


def test_cooldown_after_candidate():
    trig, buf = make(FakeScreener(), screen_interval_s=1.0)
    assert len(feed(trig, buf, scene(t_end=8.0))) == 1
    assert len(feed(trig, buf, scene(t_start=11.0, t_end=12.0))) == 1


async def test_pipeline_opens_incident_for_llm_candidate_without_ids(tmp_path):
    hub = FakeHub()

    async def on_change(incident):
        await hub.broadcast({"type": "incident.updated", "incident": incident.model_dump(mode="json")})

    service = IncidentService(IncidentStore(tmp_path / "i.db"), tmp_path / "snaps", on_change)
    camera = CameraConfig(id="CAM-02", name="Row B", location="Jalan", clip="case-2.mp4", analyse=True)
    buf = FrameBuffer()
    st = Settings(_env_file=None, gemini_api_key="k", data_dir=tmp_path, screen_interval_s=1.0)
    bare = ScreenResult(suspicious=True, score=0.9, reason="grab", suspect_track_ids=[])
    trig = GeminiTrigger(st, camera, buf, screener=FakeScreener(result=bare), blocking=False)
    pipe = CameraPipeline(camera, st, FakeDetector(), trig, MockVerifier(tmp_path / "none"), service, hub,
                          buf, source=make_source(60))
    await pipe.run()
    incidents = service.store.list()
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.status is IncidentStatus.PENDING_REVIEW
    assert inc.candidate.trigger == "llm" and inc.snapshot_files == []
    assert (inc.escape_direction, inc.escape_exit) == (None, None)
