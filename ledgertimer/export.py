"""
export.py — CSV export logic for LedgerTimer.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Sequence
import sqlite3


def _duration_decimal(start_iso: str, end_iso: str) -> str:
    """Return duration as decimal hours string, e.g. '1.75'."""
    fmt = "%Y-%m-%dT%H:%M:%S"
    start = datetime.strptime(start_iso, fmt)
    end = datetime.strptime(end_iso, fmt)
    hours = (end - start).total_seconds() / 3600
    return f"{hours:.2f}"


def export_to_csv(rows: Sequence[sqlite3.Row], filepath: str | Path) -> int:
    """
    Write rows to a CSV file.
    Returns the number of rows written.
    """
    fieldnames = ["Date", "Start Time", "End Time", "Duration", "Description", "Project"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        count = 0
        for row in rows:
            start_dt = datetime.strptime(row["start_time"], "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.strptime(row["end_time"], "%Y-%m-%dT%H:%M:%S")
            writer.writerow({
                "Date": start_dt.strftime("%Y-%m-%d"),
                "Start Time": start_dt.strftime("%H:%M"),
                "End Time": end_dt.strftime("%H:%M"),
                "Duration": _duration_decimal(row["start_time"], row["end_time"]),
                "Description": row["description"] or "",
                "Project": row["project"] or "",
            })
            count += 1

    return count
