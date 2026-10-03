"""Local history. Stores only fingerprints + sanitized summaries — never raw logs."""
from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..core.models import Diagnosis


def db_path() -> Path:
    home = Path(os.environ.get("ERRORLENS_HOME", Path.home() / ".errorlens"))
    home.mkdir(parents=True, exist_ok=True)
    return home / "history.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS incidents(
        fingerprint TEXT PRIMARY KEY, title TEXT, error_type TEXT, framework TEXT, platform TEXT,
        root_cause TEXT, first_seen TEXT, last_seen TEXT, count INTEGER DEFAULT 1, resolution TEXT)""")
    return c


def record(d: Diagnosis) -> sqlite3.Row:
    """Insert or bump the incident; returns the updated row."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with _conn() as c:
        row = c.execute("SELECT 1 FROM incidents WHERE fingerprint=?", (d.fingerprint,)).fetchone()
        if row:
            c.execute("UPDATE incidents SET count=count+1, last_seen=? WHERE fingerprint=?", (now, d.fingerprint))
        else:
            c.execute("INSERT INTO incidents(fingerprint,title,error_type,framework,platform,root_cause,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?)",
                      (d.fingerprint, d.title, d.error_type, d.context.framework, d.context.platform, d.root_cause, now, now))
        return c.execute("SELECT * FROM incidents WHERE fingerprint=?", (d.fingerprint,)).fetchone()


def search(query: str, limit: int = 20) -> list[sqlite3.Row]:
    q = f"%{query}%"
    with _conn() as c:
        return c.execute("""SELECT * FROM incidents WHERE title LIKE ? OR root_cause LIKE ? OR error_type LIKE ?
                            OR fingerprint LIKE ? ORDER BY last_seen DESC LIMIT ?""", (q, q, q, q, limit)).fetchall()


def recent(limit: int = 20) -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM incidents ORDER BY last_seen DESC, count DESC LIMIT ?", (limit,)).fetchall()


def resolve(fingerprint: str, note: str) -> bool:
    with _conn() as c:
        return c.execute("UPDATE incidents SET resolution=? WHERE fingerprint=?", (note, fingerprint)).rowcount > 0


def related(error_type: str, exclude_fp: str, limit: int = 3) -> list[dict]:
    """Other past incidents of the same error class — 'we saw something like this before'."""
    with _conn() as c:
        rows = c.execute("""SELECT fingerprint,title,count,last_seen,resolution FROM incidents
                            WHERE error_type=? AND fingerprint!=? ORDER BY count DESC, last_seen DESC LIMIT ?""",
                         (error_type, exclude_fp, limit)).fetchall()
    return [dict(r) for r in rows]
