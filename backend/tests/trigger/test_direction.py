from app.trigger.direction import escape_direction
from tests.trigger.conftest import Ent, make_scene


def test_direction_up_maps_to_exit_and_compass(camera_up_gate_b):
    ents = [Ent(2, "motorcycle", lambda t: (500, 700 - 200 * t), (120, 90))]
    history = make_scene(ents, t_end=3.0)
    assert escape_direction(history, 2, camera_up_gate_b) == ("north", "Gate B")


def test_direction_right_uses_dominant_axis(camera_up_gate_b):
    ents = [Ent(2, "motorcycle", lambda t: (100 + 300 * t, 500 - 20 * t), (120, 90))]
    history = make_scene(ents, t_end=3.0)
    assert escape_direction(history, 2, camera_up_gate_b) == ("east", "Gate A")


def test_direction_unknown_when_track_missing(camera_up_gate_b):
    history = make_scene([Ent(2, "motorcycle", lambda t: (500, 500), (120, 90))], t_end=2.0)
    assert escape_direction(history, 99, camera_up_gate_b) == (None, None)
