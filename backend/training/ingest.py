"""Register raw videos in labels.csv.

    uv run python -m training.ingest data/datasets/ucf_crime/Normal_subset --origin ucf

A video is whole-video `normal` when a folder on its path under datasets/ has "normal" in its
name (Normal_subset, online/normal) or its file name ends in _normal (staged naming). Each gets
one `normal` row. Any other video only has its source_id and phash checked and is listed as
"needs labelling"; use label_tool.py to mark the segments. Existing rows are never changed or duplicated.
"""
import argparse
import hashlib
from pathlib import Path

from training.labels import (
    DATASETS_DIR, LABELS_PATH, VIDEO_SUFFIXES, LabelRow, read_labels, video_duration, write_labels,
)
from training.phash import hamming, video_phash

NEAR_DUPLICATE_DISTANCE = 6


def make_source_id(origin: str, path: Path, phash: str) -> str:
    if origin == "online":  # content-derived: a re-download under a new name is the same source
        return "yt_" + hashlib.sha1(phash.encode()).hexdigest()[:8]
    prefix = {"ucf": "ucf", "staged": "staged", "feedback": "fb"}[origin]
    return f"{prefix}_{path.stem}"


def rel_path(path: Path, root: Path) -> str:
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def is_normal_video(rel: str) -> bool:
    parts = Path(rel).parts
    return any("normal" in d.lower() for d in parts[:-1]) or Path(rel).stem.lower().endswith(
        "_normal")


def ingest_folder(folder: Path, origin: str, labels_path: Path = LABELS_PATH,
                  root: Path = DATASETS_DIR, angle: str = "unknown",
                  light: str = "unknown") -> list[LabelRow]:
    """Returns the rows added."""
    folder = Path(folder)
    rows = read_labels(labels_path)
    known_files = {r.file for r in rows}
    known_sources = {r.source_id for r in rows}
    added: list[LabelRow] = []
    videos = sorted(p for p in folder.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES)
    for video in videos:
        rel = rel_path(video, root)
        if rel in known_files:
            print(f"skip (already registered): {rel}")
            continue
        phash = video_phash(video)
        source_id = make_source_id(origin, video, phash)
        if source_id in known_sources:
            print(f"skip (same source already registered as {source_id}): {rel}")
            continue
        near = [r.source_id for r in rows + added
                if hamming(r.phash, phash) <= NEAR_DUPLICATE_DISTANCE]
        if near:
            print(f"warning: {rel} looks like a near-duplicate of {near[0]}; "
                  "build_dataset will keep them in one split")
        if not is_normal_video(rel):
            print(f"needs labelling: {rel} (source_id {source_id})")
            continue
        added.append(LabelRow(source_id=source_id, file=rel, start=0.0, end=video_duration(video),
                              label="normal", origin=origin, angle=angle, light=light,
                              phash=phash))
        known_sources.add(source_id)
    if added:
        write_labels(labels_path, rows + added)
    print(f"{len(added)} rows added, {len(videos)} videos seen in {folder}")
    return added


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--origin", required=True, choices=["ucf", "online", "staged", "feedback"])
    ap.add_argument("--angle", default="unknown", choices=["high", "eye", "unknown"])
    ap.add_argument("--light", default="unknown", choices=["day", "dusk", "night", "unknown"])
    ap.add_argument("--labels", type=Path, default=LABELS_PATH)
    ap.add_argument("--root", type=Path, default=DATASETS_DIR)
    a = ap.parse_args()
    ingest_folder(a.folder, a.origin, a.labels, a.root, a.angle, a.light)


if __name__ == "__main__":
    main()
