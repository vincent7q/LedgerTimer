"""Tests for ledgertimer.database"""

import pytest
from unittest.mock import patch

from ledgertimer import database


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a throwaway file for every test."""
    test_db = tmp_path / "test_ledger.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db()
    yield test_db


def test_init_creates_logs_table(temp_db):
    import sqlite3
    with sqlite3.connect(temp_db) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='logs'"
        ).fetchone()
    assert row is not None


def test_start_timer_returns_id():
    row_id = database.start_timer("2026-05-26T09:00:00", "Task", "ProjectA")
    assert isinstance(row_id, int)
    assert row_id > 0


def test_running_entry_has_no_end_time():
    database.start_timer("2026-05-26T09:00:00", "Task", None)
    running = database.get_running_entry()
    assert running is not None
    assert running["end_time"] is None


def test_stop_timer_clears_running():
    row_id = database.start_timer("2026-05-26T09:00:00", "Task", None)
    database.stop_timer(row_id, "2026-05-26T10:30:00")
    assert database.get_running_entry() is None


def test_description_can_be_empty():
    row_id = database.start_timer("2026-05-26T09:00:00", "", None)
    database.stop_timer(row_id, "2026-05-26T10:00:00")
    logs = database.get_all_logs()
    assert logs[0]["description"] == ""


def test_delete_log_removes_entry():
    row_id = database.start_timer("2026-05-26T09:00:00", "To delete", None)
    database.stop_timer(row_id, "2026-05-26T10:00:00")
    database.delete_log(row_id)
    assert not any(r["id"] == row_id for r in database.get_all_logs())


def test_export_query_excludes_running():
    r1 = database.start_timer("2026-05-26T09:00:00", "Done", None)
    database.stop_timer(r1, "2026-05-26T10:00:00")
    database.start_timer("2026-05-26T11:00:00", "Still running", None)

    rows = database.get_logs_for_export("2026-05-26", "2026-05-26")
    assert len(rows) == 1
    assert rows[0]["id"] == r1


def test_export_query_date_filter():
    r1 = database.start_timer("2026-05-10T09:00:00", "May 10", None)
    database.stop_timer(r1, "2026-05-10T10:00:00")
    r2 = database.start_timer("2026-06-01T09:00:00", "June 1", None)
    database.stop_timer(r2, "2026-06-01T10:00:00")

    rows = database.get_logs_for_export("2026-05-01", "2026-05-31")
    assert len(rows) == 1
    assert rows[0]["id"] == r1


def test_update_log():
    row_id = database.start_timer("2026-05-26T09:00:00", "Original", "Old")
    database.stop_timer(row_id, "2026-05-26T10:00:00")
    database.update_log(row_id, "2026-05-26T08:00:00", "2026-05-26T09:30:00", "Updated", "New")
    logs = database.get_all_logs()
    updated = next(r for r in logs if r["id"] == row_id)
    assert updated["description"] == "Updated"
    assert updated["project"] == "New"
    assert updated["start_time"] == "2026-05-26T08:00:00"


# ---------------------------------------------------------------------------
# v2.0 tests
# ---------------------------------------------------------------------------

def test_init_creates_pause_columns(temp_db):
    import sqlite3
    with sqlite3.connect(temp_db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(logs)").fetchall()}
    assert "paused_duration" in cols
    assert "paused_at" in cols


def test_pause_timer_sets_paused_at():
    row_id = database.start_timer("2026-05-26T09:00:00", "Task", None)
    database.pause_timer(row_id, "2026-05-26T09:30:00")
    running = database.get_running_entry()
    assert running["paused_at"] == "2026-05-26T09:30:00"


def test_resume_timer_accumulates_paused_duration():
    row_id = database.start_timer("2026-05-26T09:00:00", "Task", None)
    database.pause_timer(row_id, "2026-05-26T09:30:00")
    # 10 minutes paused
    database.resume_timer(row_id, "2026-05-26T09:40:00")
    running = database.get_running_entry()
    assert running["paused_at"] is None
    assert running["paused_duration"] == 600  # 10 min in seconds


def test_resume_timer_accumulates_across_multiple_pauses():
    row_id = database.start_timer("2026-05-26T09:00:00", "Task", None)
    database.pause_timer(row_id, "2026-05-26T09:10:00")
    database.resume_timer(row_id, "2026-05-26T09:15:00")   # 5 min
    database.pause_timer(row_id, "2026-05-26T09:30:00")
    database.resume_timer(row_id, "2026-05-26T09:37:00")   # 7 min
    running = database.get_running_entry()
    assert running["paused_duration"] == 720  # 12 min total


def test_insert_log_creates_completed_entry():
    row_id = database.insert_log(
        "2026-05-26T09:00:00", "2026-05-26T10:30:00", "Manual", "ClientX"
    )
    assert isinstance(row_id, int)
    logs = database.get_all_logs()
    entry = next(r for r in logs if r["id"] == row_id)
    assert entry["end_time"] == "2026-05-26T10:30:00"
    assert entry["project"] == "ClientX"


def test_get_filtered_logs_by_project():
    r1 = database.insert_log("2026-05-26T09:00:00", "2026-05-26T10:00:00", "A", "Alpha")
    database.insert_log("2026-05-26T11:00:00", "2026-05-26T12:00:00", "B", "Beta")
    rows = database.get_filtered_logs(project="Alpha")
    assert len(rows) == 1
    assert rows[0]["id"] == r1


def test_get_filtered_logs_by_date_range():
    r1 = database.insert_log("2026-05-10T09:00:00", "2026-05-10T10:00:00", "May", None)
    database.insert_log("2026-06-01T09:00:00", "2026-06-01T10:00:00", "June", None)
    rows = database.get_filtered_logs(start_date="2026-05-01", end_date="2026-05-31")
    assert len(rows) == 1
    assert rows[0]["id"] == r1


def test_get_filtered_logs_by_keyword():
    r1 = database.insert_log("2026-05-26T09:00:00", "2026-05-26T10:00:00", "design review", None)
    database.insert_log("2026-05-26T11:00:00", "2026-05-26T12:00:00", "standup", None)
    rows = database.get_filtered_logs(keyword="design")
    assert len(rows) == 1
    assert rows[0]["id"] == r1


def test_get_filtered_logs_no_filters_returns_all():
    database.insert_log("2026-05-26T09:00:00", "2026-05-26T10:00:00", "A", None)
    database.insert_log("2026-05-26T11:00:00", "2026-05-26T12:00:00", "B", None)
    rows = database.get_filtered_logs()
    assert len(rows) == 2
