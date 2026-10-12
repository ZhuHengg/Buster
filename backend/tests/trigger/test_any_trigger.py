import logging
from datetime import datetime, timezone

from app.config import CameraConfig, Settings
from app.models import CandidateEvent, FrameDetections
from app.trigger import make_trigger
from app.trigger.any_trigger import AnyTrigger
from app.trigger.gemini_trigger import GeminiTrigger
from app.trigger.snatch_rule import SnatchRule
from app.video.buffer import FrameBuffer

CAMERA = CameraConfig(id="C", name="n", location="l")


def fd(pts: float, loop: int = 0) -> FrameDetections:
    return FrameDetections(camera_id="C", pts=pts, frame_w=10, frame_h=10, tracks=[], loop=loop)


class Scripted:
    def __init__(self, fire_at: set[float], source: str = "rule"):
        self.fire_at, self.source, self.resets, self.updates = fire_at, source, 0, 0

    def update(self, f):
        self.updates += 1
        if f.pts in self.fire_at:
            return CandidateEvent(camera_id="C", pts=f.pts, loop=f.loop, trigger=self.source,
                                  suspect_track_ids=[], detected_at=datetime.now(timezone.utc))
        return None

    def reset(self):
        self.resets += 1


def test_any_trigger_one_candidate_when_both_fire():
    a, b = Scripted({1.0}, "rule"), Scripted({1.0}, "llm")
    trig = AnyTrigger([a, b], cooldown_s=10.0)
    assert trig.update(fd(0.0)) is None
    c = trig.update(fd(1.0))
    assert c is not None and c.trigger == "rule"
    assert a.updates == 2 and b.updates == 2  # both saw every frame


def test_any_trigger_cooldown_applies_across_triggers():
    a, b = Scripted({1.0}, "rule"), Scripted({5.0}, "llm")
    trig = AnyTrigger([a, b], cooldown_s=10.0)
    assert trig.update(fd(1.0)) is not None
    assert trig.update(fd(5.0)) is None  # b fires inside a's cooldown
    b.fire_at = {12.0}
    assert trig.update(fd(12.0)) is not None


def test_any_trigger_reset_resets_all():
    a, b = Scripted(set()), Scripted(set())
    AnyTrigger([a, b]).reset()
    assert (a.resets, b.resets) == (1, 1)


def test_any_trigger_cooldown_cleared_by_reset():
    a = Scripted({1.0, 2.0})
    trig = AnyTrigger([a], cooldown_s=10.0)
    assert trig.update(fd(1.0)) is not None
    trig.reset()
    assert trig.update(fd(2.0)) is not None


def test_make_trigger_without_key_returns_rule(caplog):
    s = Settings(_env_file=None, gemini_api_key=None, triggers="both")
    with caplog.at_level(logging.WARNING):
        trig = make_trigger(s, CAMERA, FrameBuffer())
    assert isinstance(trig, SnatchRule)
    assert any("GEMINI_API_KEY" in r.message for r in caplog.records)


def test_make_trigger_rule_setting_returns_rule():
    s = Settings(_env_file=None, gemini_api_key="k", triggers="rule")
    assert isinstance(make_trigger(s, CAMERA, FrameBuffer()), SnatchRule)


def test_make_trigger_llm_returns_gemini_trigger():
    s = Settings(_env_file=None, gemini_api_key="k", triggers="llm")
    assert isinstance(make_trigger(s, CAMERA, FrameBuffer()), GeminiTrigger)


def test_make_trigger_both_returns_any_trigger():
    s = Settings(_env_file=None, gemini_api_key="k", triggers="both")
    assert isinstance(make_trigger(s, CAMERA, FrameBuffer()), AnyTrigger)


def test_any_trigger_cooldown_cleared_on_loop_change():
    a = Scripted({1.0})
    trig = AnyTrigger([a], cooldown_s=10.0)
    assert trig.update(fd(1.0, loop=0)) is not None
    a.fire_at = {2.0}
    assert trig.update(fd(2.0, loop=1)) is not None  # clip wrapped: pts restarted, cooldown must too


def test_quiet_period_setting_reaches_every_trigger():
    # after an alert the camera stays quiet for ALERT_QUIET_S: Rule B, the Gemini trigger (which also
    # stops calling Gemini, saving quota) and the combined trigger all use the same number
    q = 37.0
    rule = make_trigger(Settings(_env_file=None, triggers="rule", alert_quiet_s=q), CAMERA, FrameBuffer())
    assert rule.params.cooldown_s == q
    llm = make_trigger(Settings(_env_file=None, triggers="llm", gemini_api_key="k", alert_quiet_s=q), CAMERA,
                       FrameBuffer())
    assert llm.cooldown_s == q
    both = make_trigger(Settings(_env_file=None, triggers="both", gemini_api_key="k", alert_quiet_s=q), CAMERA,
                        FrameBuffer())
    assert both.cooldown_s == q and both.triggers[0].params.cooldown_s == q and both.triggers[1].cooldown_s == q


def test_default_quiet_period_is_longer_than_the_aftermath_of_a_snatch():
    assert Settings(_env_file=None).alert_quiet_s >= 30.0
