"""Guard feedback loop: rejected alerts become new `normal` training rows (origin=feedback).

    uv run python scripts/export_feedback.py                              # guard-REJECTED incidents
    uv run python scripts/export_feedback.py --include-ai-rejected --confirm   # + AI_REJECTED, each reviewed

Only appends to labels.csv and never edits a row. An incident already exported (source_id fb_<incident id>)
is skipped, so the script can run repeatedly. Incidents from the demo clips are never exported, which keeps
the rule that demo clips do not reach training. Snapshots are not used: only the clip file and its segment.
An AI_REJECTED incident is not automatically a negative (the AI may have missed a real snatch), so those
are exported only when a human confirms each one.
"""
import argparse
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR, CameraConfig, load_cameras  # noqa: E402
from app.incidents.store import IncidentStore  # noqa: E402
from app.models import Incident, IncidentStatus  # noqa: E402
from training.labels import DATASETS_DIR, LABELS_PATH, LabelRow, read_labels, video_duration, write_labels  # noqa: E402
from training.phash import video_phash  # noqa: E402
from training.splits import assert_no_demo_clips  # noqa: E402

MIN_SEGMENT_S = 0.5
Confirm = Callable[[Incident, Path], str]  # returns "y" (it is normal), "n" (a real snatch) or "skip"


@dataclass
class ExportResult:
    appended: list[LabelRow] = field(default_factory=list)
    skipped_demo: int = 0
    skipped_existing: int = 0
    skipped_unusable: int = 0  # clip missing, or no usable segment left after clamping
    skipped_unconfirmed: int = 0
    flagged_real: list[str] = field(default_factory=list)  # AI_REJECTED incidents a human says were real


def export_feedback(
    store: IncidentStore,
    cameras: list[CameraConfig],
    data_dir: Path,
    labels_path: Path = LABELS_PATH,
    datasets_dir: Path = DATASETS_DIR,
    include_ai_rejected: bool = False,
    confirm: Confirm | None = None,
) -> ExportResult:
    if include_ai_rejected and confirm is None:
        raise ValueError("--include-ai-rejected needs --confirm: an AI verdict is never exported unreviewed")
    data_dir, datasets_dir = Path(data_dir), Path(datasets_dir)
    demo_clips = {c.clip for c in cameras if c.clip}
    existing = read_labels(labels_path)
    known = {r.source_id for r in existing}
    result = ExportResult()
    pending: list[tuple[LabelRow, Path]] = []  # (row, source clip), copied only once every check has passed

    statuses = [IncidentStatus.REJECTED] + ([IncidentStatus.AI_REJECTED] if include_ai_rejected else [])
    for status in statuses:
        for inc in reversed(store.list(status)):  # oldest first
            source_id = f"fb_{inc.id}"
            if source_id in known:
                result.skipped_existing += 1
                continue
            if Path(inc.clip_file).name in demo_clips:
                result.skipped_demo += 1
                continue
            clip = data_dir / inc.clip_file
            if not clip.is_file():
                print(f"skip {inc.id}: clip {inc.clip_file} not found")
                result.skipped_unusable += 1
                continue
            end = min(inc.clip_end, video_duration(clip))
            if end - inc.clip_start < MIN_SEGMENT_S:
                print(f"skip {inc.id}: nothing left of segment {inc.clip_start:.1f}-{inc.clip_end:.1f}s")
                result.skipped_unusable += 1
                continue
            if status is IncidentStatus.AI_REJECTED:
                answer = confirm(inc, clip)
                if answer == "n":
                    result.flagged_real.append(inc.id)
                    continue
                if answer != "y":
                    result.skipped_unconfirmed += 1
                    continue
                notes = f"AI rejected, human confirmed normal {(inc.guard_decision_at or inc.created_at):%Y-%m-%d}"
            else:
                notes = f"guard rejected {(inc.guard_decision_at or inc.created_at):%Y-%m-%d}"
            row = LabelRow(
                source_id=source_id, file=f"feedback/{source_id}{clip.suffix.lower()}", start=inc.clip_start,
                end=end, label="normal", origin="feedback", phash=video_phash(clip), notes=notes,
            )
            pending.append((row, clip))
            known.add(source_id)

    if pending:
        assert_no_demo_clips(existing + [r for r, _ in pending], cameras, data_dir)  # also catches renamed copies
        (datasets_dir / "feedback").mkdir(parents=True, exist_ok=True)
        for row, clip in pending:
            shutil.copy2(clip, datasets_dir / row.file)
        write_labels(labels_path, existing + [r for r, _ in pending])
    result.appended = [r for r, _ in pending]
    print(f"skipped {result.skipped_demo} demo-clip incidents")
    return result


def play_and_ask(inc: Incident, clip: Path) -> str:
    """Loops the incident's segment in a window until a key is pressed, then asks in the terminal."""
    import cv2

    cap = cv2.VideoCapture(str(clip))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    start, end = int(inc.clip_start * fps), int(inc.clip_end * fps)
    title = f"{inc.id}: is this NORMAL? (any key to answer)"
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        pos = start
        while True:
            ok, frame = cap.read()
            if not ok or pos >= end:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start)
                pos = start
                continue
            pos += 1
            cv2.imshow(title, frame)
            if cv2.waitKey(int(1000 / fps)) & 0xFF != 0xFF:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    while True:
        answer = input(f"{inc.id} ({inc.camera_id}): normal? [y/n/skip] ").strip().lower()
        if answer in ("y", "n", "skip"):
            return answer


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--include-ai-rejected", action="store_true")
    ap.add_argument("--confirm", action="store_true", help="review each AI_REJECTED clip before exporting it")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--labels", type=Path, default=LABELS_PATH)
    a = ap.parse_args()
    if a.include_ai_rejected and not a.confirm:
        print("--include-ai-rejected needs --confirm: an AI verdict is never exported unreviewed")
        return 2
    store = IncidentStore(a.db or a.data_dir / "incidents.db")
    cameras = load_cameras(a.data_dir / "cameras.json")
    result = export_feedback(
        store, cameras, a.data_dir, a.labels, include_ai_rejected=a.include_ai_rejected,
        confirm=play_and_ask if a.confirm else None,
    )
    print(f"appended {len(result.appended)} row(s) to {a.labels}")
    if result.skipped_existing:
        print(f"skipped {result.skipped_existing} already exported")
    if result.skipped_unusable:
        print(f"skipped {result.skipped_unusable} with a missing clip or no usable segment")
    if result.flagged_real:
        print(f"{len(result.flagged_real)} AI-rejected incident(s) were real snatches; label them with "
              f"training.label_tool: {', '.join(result.flagged_real)}")
    if result.appended:
        print("Re-run Phase 2 Tasks 2–4 to retrain with feedback.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
