"""
database.py — SQLite data layer for LedgerTimer.
Auto-creates the database and tables on first run.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "ledger.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't already exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time  TEXT NOT NULL,
                end_time    TEXT,
                description TEXT NOT NULL DEFAULT '',
                project     TEXT
            )
        """)
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
