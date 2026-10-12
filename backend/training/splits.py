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


def _quotas(n: int, fractions: tuple[float, float, float]) -> dict[str, int]:
    if n >= 3:
        n_val, n_test = max(1, round(n * fractions[1])), max(1, round(n * fractions[2]))
        while n_val + n_test > n - 1:
            n_val, n_test = max(1, n_val - 1), max(1, n_test - 1)
    else:
        n_val, n_test = 0, 1 if n == 2 else 0
    return {"val": n_val, "test": n_test, "train": n - n_val - n_test}


def _assign(
    groups: list[list[str]], fractions: tuple[float, float, float], rng: random.Random, existing: dict[str, str]
) -> dict[str, str]:
    """Groups already placed (any member in `existing`) keep that split; new groups fill the splits'
    remaining quota, largest deficit first (ties: val, test, train)."""
    quotas = _quotas(len(groups), fractions)
    counts = {"val": 0, "test": 0, "train": 0}
    out: dict[str, str] = {}
    pending: list[list[str]] = []
    for g in groups:
        placed = {existing[s] for s in g if s in existing}
        if len(placed) > 1:
            raise ValueError(f"near-duplicate sources {g} are already in different splits {sorted(placed)}")
        if placed:
            split = placed.pop()
            counts[split] += 1
            out.update({s: split for s in g})
        else:
            pending.append(g)
    rng.shuffle(pending)
    for g in pending:
        split = max(("val", "test", "train"), key=lambda k: quotas[k] - counts[k])
        counts[split] += 1
        out.update({s: split for s in g})
    return out


def split_sources(
    rows: list[LabelRow],
    seed: int = 42,
    fractions: tuple[float, float, float] = (0.7, 0.15, 0.15),
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    """source_id -> "train" | "val" | "test". Near-duplicates share a split. Groups containing a
    snatch segment are spread first so every split gets snatch sources when there are at least 3.
    Pass the previous mapping as `existing` so adding labels never moves a source between splits."""
    existing = existing or {}
    snatch_ids = {r.source_id for r in rows if r.label == "snatch"}
    groups = source_groups(rows)
    snatch_groups = [g for g in groups if snatch_ids.intersection(g)]
    other_groups = [g for g in groups if not snatch_ids.intersection(g)]
    rng = random.Random(seed)
    out = _assign(snatch_groups, fractions, rng, existing)
    out.update(_assign(other_groups, fractions, rng, existing))
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
