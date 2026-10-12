"""Loads the generated report files for GET /api/reports. A missing or unreadable file is None, never an error."""
import csv
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

GENERATED_HINT = (
    "uv run python scripts/benchmark.py --set both   |   "
    "uv run python scripts/scale_test.py --clip data/case-2.mp4 --analyse-fps 10"
)


def _reject_constant(name: str):
    raise ValueError(f"{name} is not valid JSON")  # Python writes Infinity/NaN; browsers and the API cannot use them


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("ignoring unreadable report %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning("ignoring report %s: expected a JSON object", path)
        return None
    return data


def _baseline(raw: dict | None) -> dict | None:
    """baseline.json is hand-edited from interviews; anything that is not a real number becomes null."""
    if raw is None:
        return None
    value = raw.get("time_to_notice_s")
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return {"time_to_notice_s": value if is_number else None, "source": raw.get("source")}


def _feedback_rows(labels_path: Path | None) -> int:
    if labels_path is None or not Path(labels_path).exists():
        return 0
    with Path(labels_path).open(newline="", encoding="utf-8") as f:
        return sum(1 for rec in csv.DictReader(f) if rec.get("origin") == "feedback")


def load_reports(reports_dir: Path, labels_path: Path | None = None) -> dict:
    reports_dir = Path(reports_dir)
    return {
        "benchmark": _read_json(reports_dir / "benchmark.json"),
        "scale": _read_json(reports_dir / "scale.json"),
        "baseline": _baseline(_read_json(reports_dir / "baseline.json")),
        "feedback_rows": _feedback_rows(labels_path),
        "generated_hint": GENERATED_HINT,
    }
