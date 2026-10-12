"""Event-level metrics shared by the Gemini screener benchmark and (later) the action model."""
import math

NO_SCORE = -math.inf  # a step that is not suspicious: it can never reach a threshold
Scores = list[tuple[float, float]]  # (time_s, score)
Events = list[tuple[float, float]]  # (start_s, end_s)
VideoScores = tuple[Scores, Events, float]  # scores, snatch events, hours of non-event footage


def event_hits(
    scores: Scores,
    events: Events,
    threshold: float,
    consecutive: int = 2,
    tolerance_s: float = 1.5,
    cooldown_s: float = 10.0,
) -> tuple[int, int]:
    """Returns (events hit, false triggers).

    A trigger is `consecutive` consecutive scores >= threshold, stamped at the last of them.
    Triggers within `cooldown_s` of the previous kept trigger are merged. A trigger inside
    [start - tolerance, end + tolerance] of an event is a hit for that event (each event counts
    once; extra triggers on an already-hit event are neither hits nor false); otherwise it is false.
    """
    triggers: list[float] = []
    run = 0
    for t, s in sorted(scores):
        run = run + 1 if s >= threshold else 0
        if run >= consecutive:
            run = 0
            if not triggers or t - triggers[-1] >= cooldown_s:
                triggers.append(t)
    hit: set[int] = set()
    false = 0
    for t in triggers:
        matched = [i for i, (a, b) in enumerate(events) if a - tolerance_s <= t <= b + tolerance_s]
        if not matched:
            false += 1
        else:
            hit.add(matched[0])
    return len(hit), false


def choose_threshold(videos: list[VideoScores], max_false_per_hour: float = 2.0, **hit_kwargs) -> float:
    """Highest event recall among thresholds with false triggers per hour <= the limit; ties go to
    the lowest threshold. A threshold above every score always qualifies (no triggers)."""
    total_events = sum(len(ev) for _, ev, _ in videos)
    hours = sum(h for _, _, h in videos)
    if hours <= 0:
        raise ValueError("no normal footage to calibrate false triggers per hour")
    if total_events == 0:
        raise ValueError("no snatch events in this split to calibrate recall")
    all_scores = sorted({s for scores, _, _ in videos for _, s in scores if s > NO_SCORE})
    candidates = all_scores + [max(all_scores, default=0.0) + 1e-6]
    best: tuple[float, float] | None = None  # (recall, -threshold)
    best_t = candidates[-1]
    for t in candidates:
        hits = false = 0
        for scores, ev, _ in videos:
            h, f = event_hits(scores, ev, t, **hit_kwargs)
            hits, false = hits + h, false + f
        if false / hours > max_false_per_hour:
            continue
        key = (hits / total_events, -t)
        if best is None or key > best:
            best, best_t = key, t
    return best_t


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))
