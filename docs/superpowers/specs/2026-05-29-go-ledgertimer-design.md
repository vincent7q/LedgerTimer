# Go LedgerTimer — Design Spec

**Date:** 2026-05-29  
**Status:** Approved

---

## Overview

A Go rewrite of LedgerTimer using the Walk GUI framework (native Windows controls). The goal is a simpler, cleaner UI focused on time tracking — with History and Export accessible from a menu bar rather than always visible on screen.

The Go version lives in the `go/` subfolder of the repository. It produces a single `LedgerTimer.exe` with no runtime dependencies.

---

## Architecture

**File layout (`go/`):**

```
go/
├── main.go      — Walk MainWindow, menu bar, app entry point
├── db.go        — SQLite data layer
├── ui.go        — widget construction and view-switching logic
├── export.go    — CSV export logic
└── go.mod / go.sum
```

**SQLite driver:** `modernc.org/sqlite` — pure Go, no CGO, no MinGW required. Compatible with existing Python-created `ledger.db` files (same schema and datetime string format).

**Build command:**
```
go build -ldflags="-H windowsgui" -o LedgerTimer.exe .
```

---

## UI Design

### Main view (default on launch)

```
┌─────────────────────────────────────────┐
│ File    History    Export                │
├─────────────────────────────────────────┤
│                                         │
│  Project:  [________________▼]          │
│                                         │
│  Description:  [____________________]   │
│                                         │
│        [ ▶  Start ]                     │
│                                         │
│          00:00:00                        │  (hidden when idle)
│        [ ✕  Discard ]                   │  (hidden when idle)
│                                         │
└─────────────────────────────────────────┘
```

- Project is a combobox populated from distinct non-null project names in the DB.
- Description is a plain text entry field (optional).
- Clock label is hidden when no timer is running; shown and ticking once started.
- A "Discard" button appears below the clock while a timer is running (discards without saving).

### History view (click History in the menu bar)

Replaces the main content panel. Shows a scrollable table of all log entries, newest first.

Columns: Date | Start | End | Duration | Description | Project | [Edit] [Delete]

- Edit opens a modal dialog with fields for Date, Start Time, End Time, Description, Project.
- Delete prompts for confirmation before removing the entry.
- A **← Back** button returns to the main timer view.

### Export view (Export menu)

Replaces the main content panel.

```
  From: [YYYY-MM-DD]   To: [YYYY-MM-DD]
  
         [ Export to CSV ]
```

- Defaults to first and last day of the current month.
- Only completed entries (with an end time) within the date range are exported.
- A **← Back** button returns to the main timer view.

### View switching

Implemented by showing/hiding Walk `Composite` panels within a single `MainWindow`. No window replacement or navigation stack — just toggling `.SetVisible()`.

---

## Data Layer (`db.go`)

**Schema** (identical to Python version):

```sql
CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time  TEXT NOT NULL,
    end_time    TEXT,
    description TEXT NOT NULL DEFAULT '',
    project     TEXT
)
```

**Datetime format:** `2006-01-02T15:04:05` (Go reference time equivalent of Python's `%Y-%m-%dT%H:%M:%S`).

**DB file location:**
- Same directory as the `.exe` (resolved via `os.Executable()`).
- Falls back to current working directory if resolution fails.

**Functions:**
- `InitDB()` — create table if not exists
- `StartTimer(start, desc, project) int64` — insert running entry, return row ID
- `StopTimer(id, end)` — set end_time
- `GetRunningEntry() *LogEntry` — return entry with no end_time, or nil
- `GetAllLogs() []LogEntry` — all entries, newest first
- `GetLogsForExport(from, to) []LogEntry` — completed entries in date range
- `UpdateLog(id, start, end, desc, project)` — full row update
- `DeleteLog(id)` — remove entry
- `GetDistinctProjects() []string` — sorted distinct project names

---

## Timer Logic (`ui.go`)

**Start:**
1. Call `db.StartTimer()` → store returned ID and start timestamp in app state.
2. Switch button to "■ Stop" (red).
3. Show clock label and Discard button.
4. Launch `time.Ticker` goroutine (1s interval) → update clock via `walk.App().Synchronize()`.

**Stop:**
1. Call `db.StopTimer()`.
2. Stop ticker goroutine.
3. Clear description field, hide clock and Discard button, switch button back to "▶ Start".
4. Refresh History list if it is currently visible.

**Discard:** Confirm → `db.DeleteLog()` → same UI reset as Stop, no history refresh needed.

**Crash recovery on startup:** Call `GetRunningEntry()` — if a running entry exists, restore `_runningID`, `_runningStart`, populate fields, start ticking.

**Live field sync:** `description` and `project` field change handlers call `db.UpdateLog()` immediately (no end_time change) so state is preserved if the app exits unexpectedly.

---

## Export (`export.go`)

Writes a CSV with headers: `Date, Start Time, End Time, Duration, Description, Project`.

Duration is decimal hours rounded to 2 decimal places (e.g. `1.75` for 1h 45m).

Encoding: UTF-8. Uses Go's `encoding/csv` package.

---

## Compatibility

- Existing `ledger.db` files created by the Python version are fully compatible — same schema, same datetime string format.
- CSV output format is identical to the Python version.

---

## Out of Scope

- macOS / Linux builds (Walk is Windows-only; cross-platform can be a future effort).
- Dark mode theming (Walk uses native Windows controls which follow the system theme automatically).
- Any features not present in the Python version.
