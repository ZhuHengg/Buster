import math
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models import CandidateEvent, FrameDetections, Track

LEFT_WRIST, RIGHT_WRIST = 9, 10


@dataclass
class SnatchParams:
    window_s: float = 3.0
    proximity_ratio: float = 1.0  # moto-to-pedestrian centre distance <= ratio * pedestrian height
    reach_ratio: float = 0.35  # rider wrist to pedestrian bbox <= ratio * pedestrian height
    jerk_ratio: float = 0.25  # pedestrian centre moves >= ratio * own height within 0.3 s
    accel_ratio: float = 1.5  # moto speed after contact >= ratio * speed before
    cooldown_s: float = 10.0
    min_track_frames: int = 5


@dataclass
class _Pair:
    contact_pts: float
    grab: bool = False


def _centre(t: Track) -> tuple[float, float]:
    x1, y1, x2, y2 = t.bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def _height(t: Track) -> float:
    return t.bbox[3] - t.bbox[1]


def _inside_expanded(point: tuple[float, float], bbox, expand: float = 0.2) -> bool:
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    return (
        x1 - expand * w <= point[0] <= x2 + expand * w
        and y1 - expand * h <= point[1] <= y2 + expand * h
    )


def _point_to_bbox(px: float, py: float, bbox) -> float:
    x1, y1, x2, y2 = bbox
    return math.hypot(max(x1 - px, 0.0, px - x2), max(y1 - py, 0.0, py - y2))


@dataclass
class SnatchRule:
    """Rule B: motorcycle contact + rider grab (or victim jerk) + getaway within a short window."""

    params: SnatchParams = field(default_factory=SnatchParams)

    def __post_init__(self) -> None:
        self.diagnostics: dict[str, bool] = {"contact": False, "grab": False, "getaway": False}
        self.reset()
        self._loop: int | None = None

    def reset(self) -> None:
        self._history: deque[FrameDetections] = deque()
        self._seen: Counter[int] = Counter()
        self._pairs: dict[tuple[int, int], _Pair] = {}
        self._cooldown_until = -math.inf
        self._loop = None

    # -- helpers -------------------------------------------------------------------------
    def _positions(self, track_id: int, t0: float, t1: float) -> list[tuple[float, tuple[float, float]]]:
        out = []
        for fd in self._history:
            if t0 <= fd.pts <= t1:
                for tr in fd.tracks:
                    if tr.id == track_id:
                        out.append((fd.pts, _centre(tr)))
        return out

    def _speed(self, track_id: int, t0: float, t1: float, min_dt: float) -> float | None:
        pos = self._positions(track_id, t0, t1)
        if len(pos) < 2:
            return None
        dt = pos[-1][0] - pos[0][0]
        if dt < min_dt:
            return None
        (xa, ya), (xb, yb) = pos[0][1], pos[-1][1]
        return math.hypot(xb - xa, yb - ya) / dt

    def _jerk(self, ped: Track, now: float) -> bool:
        past = self._positions(ped.id, now - 0.4, now - 0.2)
        if not past:
            return False
        cx, cy = _centre(ped)
        px, py = past[0][1]
        return math.hypot(cx - px, cy - py) >= self.params.jerk_ratio * _height(ped)

    # -- main ----------------------------------------------------------------------------
    def update(self, fd: FrameDetections) -> CandidateEvent | None:
        p = self.params
        if self._loop is not None and fd.loop != self._loop:
            self.reset()
        self._loop = fd.loop
        self._history.append(fd)
        while self._history and fd.pts - self._history[0].pts > p.window_s + 2.0:
            self._history.popleft()
        for tr in fd.tracks:
            self._seen[tr.id] += 1
        self.diagnostics = {"contact": False, "grab": False, "getaway": False}

        stable = [t for t in fd.tracks if self._seen[t.id] >= p.min_track_frames]
        motos = [t for t in stable if t.cls == "motorcycle"]
        persons = [t for t in stable if t.cls == "person"]

        # riders: person centre inside a motorcycle bbox expanded by 20%
        riders: dict[int, list[Track]] = {m.id: [] for m in motos}
        rider_ids: set[int] = set()
        for person in persons:
            c = _centre(person)
            hosts = [m for m in motos if _inside_expanded(c, m.bbox)]
            if hosts:
                host = min(hosts, key=lambda m: math.dist(c, _centre(m)))
                riders[host.id].append(person)
                rider_ids.add(person.id)
        pedestrians = [t for t in persons if t.id not in rider_ids]
        ped_by_id = {t.id: t for t in pedestrians}
        moto_by_id = {m.id: m for m in motos}

        # drop stale pairs
        for key in list(self._pairs):
            m_id, p_id = key
            if (
                fd.pts - self._pairs[key].contact_pts > p.window_s
                or fd.pts < self._pairs[key].contact_pts
                or p_id not in ped_by_id
                or m_id not in moto_by_id
            ):
                del self._pairs[key]

        if fd.pts < self._cooldown_until:
            return None

        # 1) contact
        for m in motos:
            for ped in pedestrians:
                dist = math.dist(_centre(m), _centre(ped))
                if dist <= p.proximity_ratio * _height(ped) and (m.id, ped.id) not in self._pairs:
                    self._pairs[(m.id, ped.id)] = _Pair(contact_pts=fd.pts)
        if self._pairs:
            self.diagnostics["contact"] = True

        for (m_id, p_id), pair in list(self._pairs.items()):
            m, ped = moto_by_id[m_id], ped_by_id[p_id]
            ped_h = _height(ped)

            # 2) grab: rider wrist reaches the pedestrian, or the pedestrian is jerked
            if not pair.grab:
                for rider in riders.get(m_id, []):
                    for idx in (LEFT_WRIST, RIGHT_WRIST):
                        if rider.keypoints and len(rider.keypoints) > idx:
                            x, y, c = rider.keypoints[idx]
                            if c >= 0.3 and _point_to_bbox(x, y, ped.bbox) <= p.reach_ratio * ped_h:
                                pair.grab = True
                if not pair.grab and self._jerk(ped, fd.pts):
                    pair.grab = True
            if pair.grab:
                self.diagnostics["grab"] = True

            # 3) getaway: acceleration after contact, or clear separation while moving away
            c_pts = pair.contact_pts
            before = self._speed(m_id, c_pts - 1.0, c_pts, 0.3)
            after = self._speed(m_id, c_pts, min(fd.pts, c_pts + 1.0), 0.4)
            accel = (
                before is not None
                and after is not None
                and after >= p.accel_ratio * max(before, 0.1 * ped_h)
            )
            dist = math.dist(_centre(m), _centre(ped))
            earlier = self._positions(m_id, fd.pts - 0.5, fd.pts - 0.2)
            moving_away = bool(earlier) and dist > math.dist(earlier[0][1], _centre(ped))
            separated = dist >= 2 * p.proximity_ratio * ped_h and moving_away
            getaway = accel or separated
            if getaway:
                self.diagnostics["getaway"] = True

            if pair.grab and getaway:
                self._cooldown_until = fd.pts + p.cooldown_s
                self._pairs.clear()
                return CandidateEvent(
                    camera_id=fd.camera_id,
                    pts=fd.pts,
                    loop=fd.loop,
                    trigger="rule",
                    suspect_track_ids=[r.id for r in riders.get(m_id, [])],
                    victim_track_id=p_id,
                    motorcycle_track_id=m_id,
                    detected_at=datetime.now(timezone.utc),
                )
        return None
