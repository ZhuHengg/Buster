import asyncio
from pathlib import Path

import numpy as np
import pytest

from app.playback import PlaybackControl
from app.pipeline import ReplayPipeline
from tests.test_pipeline import (
    FakeDetector, FakeHub, FakeTrigger, camera, hub, make_pipeline, service, write_precomputed,  # noqa: F401
)


class ReSource:
    """A source that can be iterated again (like ClipSource): `loops` passes of `n` frames."""

    def __init__(self, n: int, loops: int = 2, fps: int = 10):
        self.n, self.loops, self.fps = n, loops, fps
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        frame = np.full((200, 200, 3), 100, dtype=np.uint8)
        for loop in range(self.loops):
            for i in range(self.n):
                yield frame.copy(), i / self.fps, loop


async def until(cond, timeout: float = 5.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("condition not reached")
        await asyncio.sleep(0.01)


# ---- the control itself ---------------------------------------------------------------------
async def test_control_starts_looping_and_reports_state():
    seen = []

    async def on_change(state):
        seen.append(state)

    c = PlaybackControl(on_change)
    assert c.snapshot() == {"loop": True, "held": False}
    await c.set_loop(False)
    assert c.snapshot()["loop"] is False and seen[-1] == {"loop": False, "held": False}


async def test_held_only_when_every_running_camera_is_held():
    c = PlaybackControl()
    c.register("A")
    c.register("B")
    await c.set_loop(False)
    waiter = asyncio.create_task(c.hold("A", c.generation))
    await until(lambda: "A" in c._held)
    assert c.snapshot()["held"] is False  # B is still playing its longer clip
    waiter2 = asyncio.create_task(c.hold("B", c.generation))
    await until(lambda: c.snapshot()["held"])
    await c.restart()
    await asyncio.gather(waiter, waiter2)
    assert c.snapshot()["held"] is False


# ---- live pipeline --------------------------------------------------------------------------
async def test_loop_off_plays_one_pass_then_holds(camera, tmp_path, service, hub):
    control = PlaybackControl()
    control.loop = False
    pipe = make_pipeline(camera, tmp_path, service, hub, ReSource(5, loops=3),
                         trigger=FakeTrigger(fire_on_call=None), control=control)
    task = asyncio.create_task(pipe.run())
    await until(lambda: control.snapshot()["held"])
    dets = hub.of_type("detections")
    assert [d["loop"] for d in dets] == [0] * 5  # the second pass was not analysed
    await asyncio.sleep(0.1)
    assert len(hub.of_type("detections")) == 5  # and nothing more arrives while held
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_restart_plays_the_clip_again_with_a_new_loop_number(camera, tmp_path, service, hub):
    control = PlaybackControl()
    control.loop = False
    det = FakeDetector()
    source = ReSource(5, loops=3)
    pipe = make_pipeline(camera, tmp_path, service, hub, source, trigger=FakeTrigger(fire_on_call=None),
                         detector=det, control=control)
    task = asyncio.create_task(pipe.run())
    await until(lambda: control.snapshot()["held"])
    await control.restart()
    await until(lambda: len(hub.of_type("detections")) == 10 and control.snapshot()["held"])
    loops = [d["loop"] for d in hub.of_type("detections")]
    assert loops[:5] == [0] * 5 and loops[5:] == [1] * 5  # the browser clears old boxes on a new loop number
    assert det.resets >= 1  # tracker state restarts with the clip
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_turning_loop_back_on_resumes_from_the_start(camera, tmp_path, service, hub):
    control = PlaybackControl()
    control.loop = False
    pipe = make_pipeline(camera, tmp_path, service, hub, ReSource(5, loops=2),
                         trigger=FakeTrigger(fire_on_call=None), control=control)
    task = asyncio.create_task(pipe.run())
    await until(lambda: control.snapshot()["held"])
    await control.set_loop(True)
    await asyncio.wait_for(task, 5)  # finite fake source: runs out after the resumed passes
    assert len(hub.of_type("detections")) > 5


async def test_loop_on_is_unchanged_default(camera, tmp_path, service, hub):
    pipe = make_pipeline(camera, tmp_path, service, hub, ReSource(5, loops=3),
                         trigger=FakeTrigger(fire_on_call=None))
    await pipe.run()
    assert [d["loop"] for d in hub.of_type("detections")] == [0] * 5 + [1] * 5 + [2] * 5


async def test_restart_while_playing_restarts_the_clip(camera, tmp_path, service, hub):
    control = PlaybackControl()
    source = ReSource(200, loops=1)  # long enough to still be playing when we restart
    pipe = make_pipeline(camera, tmp_path, service, hub, source, trigger=FakeTrigger(fire_on_call=None),
                         control=control)
    task = asyncio.create_task(pipe.run())
    await until(lambda: len(hub.of_type("detections")) >= 5)
    await control.restart()
    await until(lambda: source.iterations >= 2)
    await until(lambda: any(d["loop"] == 1 for d in hub.of_type("detections")))
    first_new = next(d for d in hub.of_type("detections") if d["loop"] == 1)
    assert first_new["pts"] == 0.0
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


# ---- replay pipeline ------------------------------------------------------------------------
async def test_replay_loop_off_holds_after_one_pass_and_restart_plays_again(camera, tmp_path, service, hub):
    path = write_precomputed(tmp_path / "precomputed", camera)
    control = PlaybackControl()
    control.loop = False
    task = asyncio.create_task(
        ReplayPipeline(camera, path, service, hub, realtime=False, verify_delay=0.0, control=control).run())
    await until(lambda: control.snapshot()["held"])
    assert {d["loop"] for d in hub.of_type("detections")} == {0}
    await control.restart()
    await until(lambda: control.snapshot()["held"] and len(hub.of_type("detections")) == 60)
    assert {d["loop"] for d in hub.of_type("detections")} == {0, 1}
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
