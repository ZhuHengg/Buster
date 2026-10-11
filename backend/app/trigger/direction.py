from app.config import CameraConfig
from app.models import FrameDetections


def escape_direction(
    history: list[FrameDetections],
    motorcycle_track_id: int,
    camera: CameraConfig,
    lookback_s: float = 1.5,
) -> tuple[str | None, str | None]:
    """(compass, exit_name) from the dominant axis of the motorcycle's recent displacement.

    Image `up` is negative y. Returns (None, None) when the track is missing or barely moved.
    A direction the camera has no mapping for yields None in that slot.
    """
    pts: list[tuple[float, float, float]] = []
    for fd in history:
        for tr in fd.tracks:
            if tr.id == motorcycle_track_id and tr.cls == "motorcycle":
                x1, y1, x2, y2 = tr.bbox
                pts.append((fd.pts, (x1 + x2) / 2, (y1 + y2) / 2))
    if len(pts) < 2:
        return None, None
    end_t = pts[-1][0]
    recent = [p for p in pts if end_t - p[0] <= lookback_s]
    if len(recent) < 2:
        return None, None
    dx = recent[-1][1] - recent[0][1]
    dy = recent[-1][2] - recent[0][2]
    if dx == 0 and dy == 0:
        return None, None
    if abs(dx) >= abs(dy):
        direction = "right" if dx > 0 else "left"
    else:
        direction = "down" if dy > 0 else "up"
    return camera.compass.get(direction), camera.exits.get(direction)
