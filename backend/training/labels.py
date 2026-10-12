"""labels.csv: one row per labelled segment of a source video."""
import csv
from pathlib import Path
from typing import Literal

import cv2
from pydantic import BaseModel, model_validator

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = BACKEND_DIR / "data" / "datasets"
LABELS_PATH = BACKEND_DIR / "data" / "labels.csv"
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
CLASSES = ["normal", "snatch"]  # fixed order everywhere
_DURATION_SLACK_S = 0.1


class LabelRow(BaseModel):
    source_id: str
    file: str  # relative to backend/data/datasets/, posix separators
    start: float
    end: float
    label: Literal["snatch", "normal"]
    origin: Literal["ucf", "online", "staged", "feedback"]
    angle: Literal["high", "eye", "unknown"] = "unknown"
    light: Literal["day", "dusk", "night", "unknown"] = "unknown"
    phash: str
    notes: str = ""

    @model_validator(mode="after")
    def _end_after_start(self) -> "LabelRow":
        if not self.end > self.start:
            raise ValueError(f"end ({self.end}) must be greater than start ({self.start})")
        return self


FIELDS = list(LabelRow.model_fields)


def read_labels(path: Path) -> list[LabelRow]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [LabelRow(**rec) for rec in csv.DictReader(f)]


def write_labels(path: Path, rows: list[LabelRow]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r.model_dump())


def video_duration(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise FileNotFoundError(f"cannot open video: {path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        return cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    finally:
        cap.release()


def validate_labels(rows: list[LabelRow], root: Path = DATASETS_DIR) -> list[str]:
    """Error messages: unknown files, end beyond the video duration, and overlapping
    segments of one file that carry different labels."""
    errors: list[str] = []
    durations: dict[str, float | None] = {}
    for r in rows:
        if r.file not in durations:
            p = Path(root) / r.file
            durations[r.file] = video_duration(p) if p.exists() else None
        dur = durations[r.file]
        if dur is None:
            errors.append(f"unknown file (missing): {r.file}")
        elif r.end > dur + _DURATION_SLACK_S:
            errors.append(f"{r.file}: end {r.end:.2f}s is beyond video duration {dur:.2f}s")
    by_file: dict[str, list[LabelRow]] = {}
    for r in rows:
        by_file.setdefault(r.file, []).append(r)
    for file, group in by_file.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a.label != b.label and a.start < b.end and b.start < a.end:
                    errors.append(
                        f"{file}: {a.label} [{a.start:.2f},{a.end:.2f}] overlaps "
                        f"{b.label} [{b.start:.2f},{b.end:.2f}]")
    return errors
