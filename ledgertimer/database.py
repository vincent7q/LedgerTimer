"""
database.py — SQLite data layer for LedgerTimer.
Auto-creates the database and tables on first run.
"""

import sqlite3
import sys
from pathlib import Path

# Resolve a stable data directory:
#   - When frozen by PyInstaller (onefile or onedir), use the folder
#     containing the .exe so the database persists next to it.
#   - During normal development, use the ledgertimer/ package folder.
if getattr(sys, "frozen", False):
    DB_PATH = Path(sys.executable).parent / "ledger.db"
else:
    DB_PATH = Path(__file__).parent / "ledger.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't already exist. Migrate older schemas."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time       TEXT NOT NULL,
                end_time         TEXT,
                description      TEXT NOT NULL DEFAULT '',
                project          TEXT,
                paused_duration  INTEGER NOT NULL DEFAULT 0,
                paused_at        TEXT
            )
        """)
        # Migrate existing databases that lack the v2.0 columns
        existing = {row[1] for row in conn.execute("PRAGMA table_info(logs)").fetchall()}
        if "paused_duration" not in existing:
            conn.execute("ALTER TABLE logs ADD COLUMN paused_duration INTEGER NOT NULL DEFAULT 0")
        if "paused_at" not in existing:
            conn.execute("ALTER TABLE logs ADD COLUMN paused_at TEXT")
        conn.commit()


# ---------------------------------------------------------------------------
# Timer control
# ---------------------------------------------------------------------------

def start_timer(start_time: str, description: str, project: str | None) -> int:
    """Insert a new running entry. Returns the new row id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO logs (start_time, description, project) VALUES (?, ?, ?)",
            (start_time, description, project or None),
        )
        conn.commit()
        return cur.lastrowid


def stop_timer(log_id: int, end_time: str) -> None:
    """Set end_time on the given log entry."""
    with _connect() as conn:
        conn.execute(
            "UPDATE logs SET end_time = ? WHERE id = ?",
            (end_time, log_id),
        )
        conn.commit()


def get_running_entry() -> sqlite3.Row | None:
    """Return the single entry with no end_time, or None."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM logs WHERE end_time IS NULL LIMIT 1"
        ).fetchone()


def pause_timer(log_id: int, paused_at: str) -> None:
    """Record the moment a running timer is paused."""
    with _connect() as conn:
        conn.execute(
            "UPDATE logs SET paused_at = ? WHERE id = ?",
            (paused_at, log_id),
        )
        conn.commit()


def resume_timer(log_id: int, resumed_at: str) -> None:
    """Accumulate the paused interval and clear paused_at."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT paused_at, paused_duration FROM logs WHERE id = ?", (log_id,)
        ).fetchone()
        if row and row["paused_at"]:
            from datetime import datetime
            _DT_FMT = "%Y-%m-%dT%H:%M:%S"
            extra = int(
                (datetime.strptime(resumed_at, _DT_FMT) -
                 datetime.strptime(row["paused_at"], _DT_FMT)).total_seconds()
            )
            new_total = (row["paused_duration"] or 0) + extra
            conn.execute(
                "UPDATE logs SET paused_at = NULL, paused_duration = ? WHERE id = ?",
                (new_total, log_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Log management
# ---------------------------------------------------------------------------

def get_all_logs() -> list[sqlite3.Row]:
    """Return all log entries, most recent first."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM logs ORDER BY start_time DESC"
        ).fetchall()


def update_log(log_id: int, start_time: str, end_time: str | None,
               description: str, project: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE logs
               SET start_time = ?, end_time = ?, description = ?, project = ?
               WHERE id = ?""",
            (start_time, end_time or None, description, project or None, log_id),
        )
        conn.commit()


def delete_log(log_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
        conn.commit()


def insert_log(start_time: str, end_time: str, description: str,
               project: str | None) -> int:
    """Insert a completed past entry. Returns the new row id."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO logs (start_time, end_time, description, project)
               VALUES (?, ?, ?, ?)""",
            (start_time, end_time, description, project or None),
        )
        conn.commit()
        return cur.lastrowid


def get_filtered_logs(project: str | None = None, start_date: str | None = None,
                      end_date: str | None = None, keyword: str | None = None
                      ) -> list[sqlite3.Row]:
    """Return logs filtered by optional project, date range, and keyword."""
    clauses = []
    params: list = []
    if project:
        clauses.append("project = ?")
        params.append(project)
    if start_date:
        clauses.append("DATE(start_time) >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("DATE(start_time) <= ?")
        params.append(end_date)
    if keyword:
        clauses.append("(description LIKE ? OR project LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return conn.execute(
            f"SELECT * FROM logs {where} ORDER BY start_time DESC",
            params,
        ).fetchall()


def get_logs_for_export(start_date: str, end_date: str) -> list[sqlite3.Row]:
    """
    Return completed logs (end_time IS NOT NULL) whose date falls within
    [start_date, end_date] inclusive. Dates as 'YYYY-MM-DD'.
    """
    with _connect() as conn:
        return conn.execute(
            """SELECT * FROM logs
               WHERE end_time IS NOT NULL
                 AND DATE(start_time) >= ?
                 AND DATE(start_time) <= ?
               ORDER BY start_time ASC""",
            (start_date, end_date),
        ).fetchall()


def get_distinct_projects() -> list[str]:
    """Return sorted list of distinct non-null project names."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT project FROM logs WHERE project IS NOT NULL ORDER BY project"
        ).fetchall()
        return [r["project"] for r in rows]
