from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import pytest


def write_video(path: Path, seconds: float = 1.0, fps: float = 10.0, seed: int = 0,
                size: tuple[int, int] = (64, 48)) -> Path:
    """Synthetic clip: a seeded random-blob background that drifts a little each frame."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    base = cv2.resize(rng.integers(0, 255, (6, 8, 3), dtype=np.uint8), size,
                      interpolation=cv2.INTER_CUBIC)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    assert writer.isOpened()
    for i in range(int(round(seconds * fps))):
        writer.write(np.roll(base, i, axis=1))
    writer.release()
    return path


@pytest.fixture
def make_video() -> Callable[..., Path]:
    return write_video
