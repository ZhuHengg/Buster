"""Leak-safe splits: whole source videos (and their near-duplicates) go to exactly one split."""
import random
from pathlib import Path

from app.config import DATA_DIR, CameraConfig
from training.labels import LabelRow
from training.phash import hamming, video_phash

NEAR_DUPLICATE_DISTANCE = 6


def source_groups(rows: list[LabelRow], max_hamming: int = NEAR_DUPLICATE_DISTANCE) -> list[list[str]]:
    """Groups of source_ids whose perceptual hashes are within max_hamming (union-find)."""
    phash: dict[str, str] = {}
    for r in rows:
        phash.setdefault(r.source_id, r.phash)
    ids = sorted(phash)
    parent = {i: i for i in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if hamming(phash[a], phash[b]) <= max_hamming:
                parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values())


def _assign(groups: list[list[str]], fractions: tuple[float, float, float], rng: random.Random) -> dict[str, str]:
    groups = groups[:]
    rng.shuffle(groups)
    n = len(groups)
    if n >= 3:
        n_val = max(1, round(n * fractions[1]))
        n_test = max(1, round(n * fractions[2]))
        while n_val + n_test > n - 1:
            n_val, n_test = max(1, n_val - 1), max(1, n_test - 1)
    else:
        n_val, n_test = 0, 1 if n == 2 else 0
    out: dict[str, str] = {}
    for i, g in enumerate(groups):
        split = "val" if i < n_val else "test" if i < n_val + n_test else "train"
        for s in g:
            out[s] = split
    return out


def split_sources(
    rows: list[LabelRow], seed: int = 42, fractions: tuple[float, float, float] = (0.7, 0.15, 0.15)
) -> dict[str, str]:
    """source_id -> "train" | "val" | "test". Near-duplicates share a split. Groups containing a
    snatch segment are spread first so every split gets snatch sources when there are at least 3."""
    snatch_ids = {r.source_id for r in rows if r.label == "snatch"}
    groups = source_groups(rows)
    snatch_groups = [g for g in groups if snatch_ids.intersection(g)]
    other_groups = [g for g in groups if not snatch_ids.intersection(g)]
    rng = random.Random(seed)
    out = _assign(snatch_groups, fractions, rng)
    out.update(_assign(other_groups, fractions, rng))
    return out


def assert_no_demo_clips(rows: list[LabelRow], cameras: list[CameraConfig], data_dir: Path = DATA_DIR) -> None:
    """Demo clips must never reach training, validation, threshold selection or benchmarks."""
    for cam in cameras:
        if not cam.clip:
            continue
        clip_path = Path(data_dir) / cam.clip
        demo_hash = video_phash(clip_path) if clip_path.exists() else None
        for r in rows:
            if Path(r.file).name == cam.clip or (
                demo_hash is not None and hamming(r.phash, demo_hash) <= NEAR_DUPLICATE_DISTANCE
            ):
                raise ValueError(f"demo clip {cam.clip} appears in the labels as {r.file} ({r.source_id})")
