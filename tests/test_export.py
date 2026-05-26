"""Tests for ledgertimer.export"""

import csv

from ledgertimer import export


class _Row(dict):
    """Minimal sqlite3.Row stand-in."""
    def __getitem__(self, key):
        return super().__getitem__(key)


def _row(start, end, description="", project=None):
    return _Row({"start_time": start, "end_time": end,
                 "description": description, "project": project})


def test_export_returns_row_count(tmp_path):
    rows = [_row("2026-05-26T09:00:00", "2026-05-26T10:30:00")]
    count = export.export_to_csv(rows, tmp_path / "out.csv")
    assert count == 1


def test_export_csv_headers(tmp_path):
    out = tmp_path / "out.csv"
    export.export_to_csv([], out)
    with open(out, newline="", encoding="utf-8") as f:
        headers = f.readline().strip().split(",")
    assert headers == ["Date", "Start Time", "End Time", "Duration", "Description", "Project"]


def test_export_csv_values(tmp_path):
    rows = [_row("2026-05-26T09:00:00", "2026-05-26T10:45:00", "Code review", "ClientB")]
    out = tmp_path / "out.csv"
    export.export_to_csv(rows, out)

    with open(out, newline="", encoding="utf-8") as f:
        data = list(csv.DictReader(f))

    assert data[0]["Date"] == "2026-05-26"
    assert data[0]["Start Time"] == "09:00"
    assert data[0]["End Time"] == "10:45"
    assert data[0]["Duration"] == "1.75"
    assert data[0]["Description"] == "Code review"
    assert data[0]["Project"] == "ClientB"


def test_export_empty_description_and_project(tmp_path):
    rows = [_row("2026-05-26T09:00:00", "2026-05-26T09:30:00")]
    out = tmp_path / "out.csv"
    export.export_to_csv(rows, out)

    with open(out, newline="", encoding="utf-8") as f:
        data = list(csv.DictReader(f))

    assert data[0]["Description"] == ""
    assert data[0]["Project"] == ""


def test_duration_calculation(tmp_path):
    # 90 minutes = 1.50 decimal hours
    rows = [_row("2026-05-26T08:00:00", "2026-05-26T09:30:00")]
    out = tmp_path / "out.csv"
    export.export_to_csv(rows, out)

    with open(out, newline="", encoding="utf-8") as f:
        data = list(csv.DictReader(f))

    assert data[0]["Duration"] == "1.50"
