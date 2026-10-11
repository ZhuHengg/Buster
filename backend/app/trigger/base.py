from typing import Protocol

from app.models import CandidateEvent, FrameDetections


class Trigger(Protocol):
    """Step 1 candidate detector. Phase 2 adds a model-based implementation."""

    def update(self, fd: FrameDetections) -> CandidateEvent | None: ...

    def reset(self) -> None: ...
