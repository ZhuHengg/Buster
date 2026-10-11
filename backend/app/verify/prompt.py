from app.config import CameraConfig
from app.models import CandidateEvent


def build_prompt(candidate: CandidateEvent, camera: CameraConfig) -> str:
    compass = ", ".join(f"image {d} = {c}" for d, c in camera.compass.items())
    ids = []
    if candidate.suspect_track_ids:
        ids.append(f"suspect track IDs {candidate.suspect_track_ids}")
    if candidate.victim_track_id is not None:
        ids.append(f"victim track ID {candidate.victim_track_id}")
    if candidate.motorcycle_track_id is not None:
        ids.append(f"motorcycle track ID {candidate.motorcycle_track_id}")
    hint = f" The detector's candidate: {'; '.join(ids)}." if ids else ""
    compass_line = f" Compass orientation of this camera: {compass}." if compass else ""
    return (
        f"These are CCTV keyframes from {camera.name}, {camera.location}, in time order, "
        f"with tracker IDs drawn on the boxes.{hint}{compass_line}\n\n"
        "Decide whether a crime is occurring, with the focus on motorcycle snatch theft "
        "(a rider or pillion grabs a bag, phone or valuables from a pedestrian and flees). "
        "Normal traffic, parked motorcycles, people walking or running, and friendly contact are not incidents.\n\n"
        "Describe suspects by clothing, helmet and build only. Never guess identity, ethnicity or names. "
        "Describe the vehicle (type, colour, plate only if clearly readable). "
        "Set escape_direction (north, south, east, west) only if the direction of escape is clearly visible, "
        "otherwise use unknown. Set is_incident false and incident_type none if no crime is happening. "
        "Reply with the JSON object that fills the schema."
    )
