"""Local SQLite sessions, adapted from the HMS locking/WAL/parameterized logging pattern."""

import json
import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path

from blindspot.sessions import Session


class SessionStore:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions "
            "(id TEXT PRIMARY KEY, created_at REAL NOT NULL, "
            "participant TEXT NOT NULL, payload TEXT NOT NULL, receipt TEXT)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS session_time ON sessions(created_at)")
        self._conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._conn.close()

    def save(self, session: Session, receipt: dict | None = None):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions VALUES (?, ?, ?, ?, ?)",
                (
                    session.id,
                    session.created_at,
                    session.participant,
                    json.dumps(asdict(session), allow_nan=False),
                    json.dumps(receipt, allow_nan=False) if receipt else None,
                ),
            )

    def get(self, session_id: str) -> Session | None:
        row = self._conn.execute(
            "SELECT payload FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        return Session.from_dict(json.loads(row[0])) if row else None

    def receipt(self, session_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT receipt FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def recent(self, limit: int = 20, offset: int = 0, participant: str | None = None):
        if not 1 <= limit <= 1000 or offset < 0:
            raise ValueError("Invalid pagination")
        where = " WHERE participant=?" if participant is not None else ""
        args = (participant,) if participant is not None else ()
        rows = self._conn.execute(
            "SELECT payload FROM sessions"
            + where
            + " ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
            (*args, limit, offset),
        ).fetchall()
        return [Session.from_dict(json.loads(row[0])) for row in rows]

    def baseline_candidates(self, session: Session, policy):
        # Filter at query time so unrelated sessions cannot crowd out valid history.
        rows = self._conn.execute(
            "SELECT payload FROM sessions WHERE participant=? AND created_at<? AND created_at>=? "
            "ORDER BY created_at DESC",
            (
                session.participant,
                session.created_at,
                session.created_at - policy.baseline_max_age_days * 86400,
            ),
        )
        return [Session.from_dict(json.loads(row[0])) for row in rows]

    def count(self):
        return self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
