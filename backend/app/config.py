import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"

Direction = Literal["left", "right", "up", "down"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_screen_model: str | None = None  # step 1 screener; falls back to gemini_model
    screen_threshold: float = 0.5
    screen_interval_s: float = 3.0
    screen_frames: int = 6
    screen_max_lag_s: float = 6.0
    triggers: Literal["rule", "llm", "both"] = "both"
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    police_number: str | None = None
    gate_number: str | None = None
    mode: Literal["live", "replay"] = "live"
    operator_name: str = "CMS Operator 1"
    data_dir: Path = DATA_DIR
    db_path: Path = DATA_DIR / "incidents.db"


class ExpectedEvent(BaseModel):
    """Where a demo clip's snatch is, in clip seconds. Used only by the benchmark."""

    start: float
    end: float


class CameraConfig(BaseModel):
    id: str
    name: str
    location: str
    clip: str | None = None
    analyse: bool = False
    exits: dict[Direction, str] = {}
    compass: dict[Direction, str] = {}
    expected_event: ExpectedEvent | None = None  # None: a normal clip (any candidate is a false alarm)


def load_cameras(path: Path) -> list[CameraConfig]:
    """Load cameras.json; clip files resolve relative to the file's folder."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cameras = [CameraConfig(**item) for item in raw]
    seen: set[str] = set()
    for cam in cameras:
        if cam.id in seen:
            raise ValueError(f"duplicate camera id: {cam.id}")
        seen.add(cam.id)
        if cam.analyse and cam.clip is not None and not (Path(path).parent / cam.clip).exists():
            raise ValueError(f"missing clip for {cam.id}: {cam.clip}")
    return cameras
