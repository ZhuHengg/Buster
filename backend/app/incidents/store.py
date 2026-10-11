import sqlite3
from contextlib import closing
from pathlib import Path

from app.models import Incident, IncidentStatus


class IncidentStore:
    """SQLite persistence: one row per incident, the full model as JSON in `body`."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS incidents ("
                "id TEXT PRIMARY KEY, status TEXT, created_at TEXT, body TEXT)"
            )

    def _connect(self) -> sqlite3.Connection:
        # a connection per call keeps this safe across threads (pipelines use to_thread)
        return sqlite3.connect(self.db_path, timeout=10)

    def save(self, incident: Incident) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO incidents (id, status, created_at, body) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, body=excluded.body",
                (incident.id, incident.status.value, incident.created_at.isoformat(), incident.model_dump_json()),
            )

    def get(self, incident_id: str) -> Incident | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT body FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return Incident.model_validate_json(row[0]) if row else None

    def list(self, status: IncidentStatus | None = None) -> list[Incident]:
        sql = "SELECT body FROM incidents"
        args: tuple = ()
        if status is not None:
            sql += " WHERE status = ?"
            args = (status.value,)
        sql += " ORDER BY created_at DESC, id DESC"
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, args).fetchall()
        return [Incident.model_validate_json(r[0]) for r in rows]

    def count_with_prefix(self, prefix: str) -> int:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT COUNT(*) FROM incidents WHERE id LIKE ?", (prefix + "%",)).fetchone()[0]
