import pytest

from training.events import choose_threshold, event_hits, wilson_interval


def series(pairs):
    return [(float(t), float(s)) for t, s in pairs]


def test_event_hits_counts_hit_within_tolerance():
    scores = series([(0, 0.1), (1, 0.9), (2, 0.9), (3, 0.1)])
    assert event_hits(scores, [(2.0, 2.5)], threshold=0.5, consecutive=2, tolerance_s=1.5) == (1, 0)


def test_event_hits_trigger_far_from_event_is_false_trigger():
    scores = series([(20, 0.9), (21, 0.9)])
    assert event_hits(scores, [(2.0, 2.5)], threshold=0.5, consecutive=2, tolerance_s=1.5) == (0, 1)


def test_event_hits_single_score_below_consecutive_not_trigger():
    scores = series([(1, 0.9), (2, 0.1), (3, 0.9), (4, 0.1)])
    assert event_hits(scores, [(1.0, 1.5)], threshold=0.5, consecutive=2) == (0, 0)


def test_event_hits_merges_within_cooldown():
    scores = series([(30, 0.9), (31, 0.9), (33, 0.9), (34, 0.9), (50, 0.9), (51, 0.9)])
    assert event_hits(scores, [], threshold=0.5, consecutive=2, cooldown_s=10.0) == (0, 2)


def test_event_hits_counts_each_event_once():
    scores = series([(1, 0.9), (2, 0.9), (13, 0.9), (14, 0.9)])
    assert event_hits(scores, [(1.0, 14.0)], threshold=0.5, consecutive=2, tolerance_s=1.0) == (1, 0)


def test_choose_threshold_respects_false_rate():
    # one normal hour with a false alarm scored 0.6; the event is scored 0.9
    video_normal = (series([(10, 0.6), (11, 0.1)]), [], 1.0)
    video_snatch = (series([(5, 0.9)]), [(4.5, 5.5)], 0.0)
    t = choose_threshold([video_normal, video_snatch], max_false_per_hour=0.5, consecutive=1)
    assert t > 0.6 and t <= 0.9


def test_choose_threshold_prefers_recall():
    video_normal = (series([(10, 0.2)]), [], 10.0)
    video_snatch = (series([(5, 0.7)]), [(4.5, 5.5)], 0.0)
    t = choose_threshold([video_normal, video_snatch], max_false_per_hour=2.0, consecutive=1)
    assert t <= 0.7  # still catches the event


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(9, 10)
    assert lo == pytest.approx(0.596, abs=0.01) and hi == pytest.approx(0.982, abs=0.01)
    assert wilson_interval(0, 0) == (0.0, 1.0)
