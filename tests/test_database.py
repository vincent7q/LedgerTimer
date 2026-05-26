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
