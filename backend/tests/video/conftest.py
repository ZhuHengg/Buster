from pathlib import Path

import cv2
import numpy as np
import pytest


@pytest.fixture
def tiny_clip(tmp_path: Path) -> Path:
    """1 s synthetic clip: 10 fps, 64x48, frame i is filled with gray level i*20."""
    path = tmp_path / "tiny.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 48))
    assert writer.isOpened()
    for i in range(10):
        writer.write(np.full((48, 64, 3), i * 20, dtype=np.uint8))
    writer.release()
    return path
