import math

from app.models import CandidateEvent, FrameDetections
from app.trigger.base import Trigger


class AnyTrigger:
    """Runs every trigger on every frame; the first candidate wins and starts one shared cooldown."""

    def __init__(self, triggers: list[Trigger], cooldown_s: float = 10.0):
        self.triggers, self.cooldown_s = triggers, cooldown_s
        self._cooldown_until = -math.inf
        self._loop: int | None = None

    def update(self, fd: FrameDetections) -> CandidateEvent | None:
        if self._loop is not None and fd.loop != self._loop:
            self._cooldown_until = -math.inf  # the clip wrapped and pts restarted
        self._loop = fd.loop
        candidates = [c for c in (t.update(fd) for t in self.triggers) if c is not None]
        if not candidates or fd.pts < self._cooldown_until:
            return None
        self._cooldown_until = fd.pts + self.cooldown_s
        return candidates[0]

    def reset(self) -> None:
        self._cooldown_until = -math.inf
        self._loop = None
        for t in self.triggers:
            t.reset()
