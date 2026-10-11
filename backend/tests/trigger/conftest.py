"""Synthetic scene builder for trigger tests (10 fps, 1000x800 frame)."""
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from app.config import CameraConfig
from app.models import FrameDetections, Track

Pos = Callable[[float], tuple[float, float]]
INF = float("inf")


@dataclass
class Ent:
    id: int
    cls: str
    pos: Pos
    size: tuple[float, float]
    wrist: Callable[[float], tuple[float, float] | None] | None = None
    t_range: tuple[float, float] = field(default=(0.0, INF))


def make_scene(
    entities: list[Ent],
    t_end: float,
    fps: int = 10,
    loop: int = 0,
    t_start: float = 0.0,
    camera_id: str = "CAM-07",
) -> list[FrameDetections]:
    n = int(round((t_end - t_start) * fps))
    frames: list[FrameDetections] = []
    for i in range(n):
        t = t_start + i / fps
        tracks: list[Track] = []
        for e in entities:
            if not (e.t_range[0] <= t <= e.t_range[1]):
                continue
            cx, cy = e.pos(t)
            w, h = e.size
            kps = None
            if e.cls == "person" and e.wrist is not None:
                kps = [(0.0, 0.0, 0.0)] * 17
                wp = e.wrist(t)
                if wp is not None:
                    kps[9] = (wp[0], wp[1], 0.9)
            tracks.append(
                Track(
                    id=e.id, cls=e.cls, bbox=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                    conf=0.9, keypoints=kps,
                )
            )
        frames.append(
            FrameDetections(camera_id=camera_id, pts=t, frame_w=1000, frame_h=800, tracks=tracks, loop=loop)
        )
    return frames


def snatch_entities(
    ped_id: int = 1, moto_id: int = 2, rider_id: int = 3, t0: float = 0.0, with_pose: bool = True,
    with_jerk: bool = False, y_off: float = 0.0,
) -> list[Ent]:
    """Pedestrian (static, 50x160 at x=500). Motorcycle approaches slowly from the left,
    rider reaches out (wrist near pedestrian) at t0+2.5..3.0, then it accelerates away to the right."""

    def moto_x(t: float) -> float:
        s = t - t0
        if s < 3.0:
            return 200 + 60 * s
        return 380 + 300 * (s - 3.0)

    def ped_pos(t: float) -> tuple[float, float]:
        s = t - t0
        if with_jerk and s > 2.6:
            return 500 + min(90.0, 300 * (s - 2.6)), 500 + y_off
        return 500, 500 + y_off

    def wrist(t: float):
        s = t - t0
        return (470.0, 450.0 + y_off) if 2.5 <= s <= 3.0 else (moto_x(t) + 30, 500.0 + y_off)

    return [
        Ent(ped_id, "person", ped_pos, (50, 160)),
        Ent(moto_id, "motorcycle", lambda t: (moto_x(t), 540 + y_off), (120, 90)),
        Ent(rider_id, "person", lambda t: (moto_x(t), 500 + y_off), (40, 80), wrist=wrist if with_pose else None),
    ]


@pytest.fixture
def camera_up_gate_b() -> CameraConfig:
    return CameraConfig(
        id="CAM-07", name="Elmina Shoplot Row B", location="Row B", clip="case-1.mp4", analyse=True,
        exits={"up": "Gate B", "right": "Gate A"},
        compass={"up": "north", "right": "east", "left": "west", "down": "south"},
    )
