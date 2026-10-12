"""Reproducibility fields shared by every generated report."""
import subprocess
from datetime import datetime, timezone

from app.config import BACKEND_DIR


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=BACKEND_DIR, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def git_commit() -> str:
    """HEAD sha, suffixed -dirty when tracked files have uncommitted changes."""
    commit = _git("rev-parse", "HEAD") or "unknown"
    if _git("status", "--porcelain", "--untracked-files=no"):
        commit += "-dirty"
    return commit


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
