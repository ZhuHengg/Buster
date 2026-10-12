"""Perceptual hash of a video: three 64-bit dHashes (10/50/90% of the clip) as 48 hex chars."""
from pathlib import Path

import cv2
import numpy as np

HASH_HEX_LEN = 48
_POSITIONS = (0.10, 0.50, 0.90)


def _dhash(frame: np.ndarray) -> int:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def video_phash(path: Path) -> str:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video: {path}")
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            raise ValueError(f"video has no frames: {path}")
        value = 0
        for pos in _POSITIONS:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, int(total * pos)))
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"cannot read frame at {pos:.0%} of {path}")
            value = (value << 64) | _dhash(frame)
        return f"{value:0{HASH_HEX_LEN}x}"
    finally:
        cap.release()


def hamming(a: str, b: str) -> int:
    """Summed Hamming distance over the three frame hashes."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")
