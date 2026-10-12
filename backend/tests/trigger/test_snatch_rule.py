import pytest

from app.trigger.snatch_rule import SnatchParams, SnatchRule
from tests.trigger.conftest import Ent, make_scene, snatch_entities


def run(rule: SnatchRule, frames):
    return [ev for fd in frames if (ev := rule.update(fd)) is not None]


def test_snatch_sequence_triggers_once():
    events = run(SnatchRule(), make_scene(snatch_entities(), t_end=8.0))
    assert len(events) == 1
    ev = events[0]
    assert ev.trigger == "rule"
    assert ev.camera_id == "CAM-07"
    assert ev.victim_track_id == 1
    assert ev.motorcycle_track_id == 2
    assert ev.suspect_track_ids == [3]
    assert 2.5 <= ev.pts <= 4.5


def test_snatch_with_jerk_but_no_pose_triggers():
    frames = make_scene(snatch_entities(with_pose=False, with_jerk=True), t_end=8.0)
    events = run(SnatchRule(), frames)
    assert len(events) == 1
    assert events[0].victim_track_id == 1


def test_motorcycle_passing_without_grab_no_trigger():
    ents = [
        Ent(1, "person", lambda t: (500, 500), (50, 160)),
        Ent(2, "motorcycle", lambda t: (-100 + 300 * t, 540), (120, 90)),
        Ent(3, "person", lambda t: (-100 + 300 * t, 500), (40, 80)),
    ]
    assert run(SnatchRule(), make_scene(ents, t_end=8.0)) == []


def test_pedestrians_walking_close_no_trigger():
    ents = [
        Ent(1, "person", lambda t: (400 + 10 * t, 500), (50, 160)),
        Ent(2, "person", lambda t: (460 + 10 * t, 500), (50, 160)),
    ]
    assert run(SnatchRule(), make_scene(ents, t_end=8.0)) == []


def test_motorcycle_parked_near_pedestrian_no_trigger():
    ents = [
        Ent(1, "person", lambda t: (500, 500), (50, 160)),
        Ent(2, "motorcycle", lambda t: (380, 540), (120, 90)),
        Ent(3, "person", lambda t: (380, 500), (40, 80), wrist=lambda t: (470.0, 450.0)),
    ]
    assert run(SnatchRule(), make_scene(ents, t_end=8.0)) == []


def test_cooldown_suppresses_second_event():
    ents = snatch_entities() + snatch_entities(ped_id=11, moto_id=12, rider_id=13, t0=5.0, y_off=300)
    events = run(SnatchRule(), make_scene(ents, t_end=13.0))
    assert len(events) == 1


def test_event_allowed_again_after_cooldown():
    ents = snatch_entities() + snatch_entities(ped_id=11, moto_id=12, rider_id=13, t0=14.0, y_off=300)
    rule = SnatchRule(SnatchParams(cooldown_s=10.0))
    events = run(rule, make_scene(ents, t_end=22.0))
    assert [e.victim_track_id for e in events] == [1, 11]


def test_loop_change_resets_and_does_not_fire_on_wrap():
    rule = SnatchRule()
    # loop 0: contact and wrist reach happened, getaway not yet
    assert run(rule, make_scene(snatch_entities(), t_end=2.9)) == []
    # loop 1: pts restarts at 0, same track ids, motorcycle far away moving off fast
    wrap = [
        Ent(1, "person", lambda t: (500, 500), (50, 160)),
        Ent(2, "motorcycle", lambda t: (900 + 300 * t, 540), (120, 90)),
        Ent(3, "person", lambda t: (900 + 300 * t, 500), (40, 80)),
    ]
    assert run(rule, make_scene(wrap, t_end=3.0, loop=1)) == []


def test_loop_change_clears_cooldown():
    rule = SnatchRule()
    assert len(run(rule, make_scene(snatch_entities(), t_end=8.0))) == 1
    again = make_scene(snatch_entities(), t_end=8.0, loop=1)
    assert len(run(rule, again)) == 1  # cooldown from loop 0 must not suppress loop 1


def test_rider_not_treated_as_victim():
    ents = [
        Ent(2, "motorcycle", lambda t: (200 + 300 * t, 540), (120, 90)),
        Ent(3, "person", lambda t: (200 + 300 * t, 500), (40, 80), wrist=lambda t: (200 + 300 * t + 30, 500.0)),
    ]
    assert run(SnatchRule(), make_scene(ents, t_end=6.0)) == []


@pytest.mark.parametrize("with_pose,with_jerk", [(True, False), (False, True)])
def test_rule_b_detects_at_analyse_fps_10_as_fast_as_at_full_rate(with_pose, with_jerk):
    """Characterisation for `analyse_fps=10`: a 30 fps scene analysed on every 3rd frame still fires,
    on either evidence path, within a frame or two of the full-rate detection. (Measured: below 10 fps the
    pose path starts missing the 0.5 s wrist-reach window; the jerk path holds down to about 5 fps.)"""
    scene = make_scene(snatch_entities(with_pose=with_pose, with_jerk=with_jerk), t_end=8.0, fps=30)
    full, sampled = run(SnatchRule(), scene), run(SnatchRule(), scene[::3])
    assert len(full) == 1 and len(sampled) == 1
    assert abs(sampled[0].pts - full[0].pts) <= 0.2
