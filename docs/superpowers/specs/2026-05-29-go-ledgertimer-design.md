# Go LedgerTimer — Design Spec

**Date:** 2026-05-29  
**Status:** Approved

---

## Overview

A Go rewrite of LedgerTimer using the **Fyne** GUI framework — cross-platform, single codebase, builds natively on Windows, macOS, and Linux. The goal is a simpler, cleaner UI focused on time tracking — with History and Export accessible from a menu bar rather than always visible on screen.

The Go version lives in the `go/` subfolder of the repository. It produces a single self-contained binary on each platform.

---

## Architecture

**File layout (`go/`):**

```
go/
├── main.go      — Fyne app, window, menu bar, entry point
├── db.go        — SQLite data layer
├── ui.go        — widget construction and view-switching logic
├── export.go    — CSV export logic
└── go.mod / go.sum
```

**Dependencies:**
- `fyne.io/fyne/v2` — cross-platform GUI (OpenGL-based, follows system light/dark theme)
- `modernc.org/sqlite` — pure Go SQLite, no CGO required for the DB layer

> **Note:** Fyne itself requires a C compiler for its rendering backend (OpenGL). See Build Requirements below.

---

## Build Requirements

A C compiler is needed on each platform for Fyne's graphics backend.

| Platform | Requirement |
|----------|-------------|
| Windows  | [TDM-GCC](https://jmeubank.github.io/tdm-gcc/) or MinGW-w64 |
| macOS    | Xcode Command Line Tools (`xcode-select --install`) |
| Linux    | `gcc`, `libgl1-mesa-dev`, `xorg-dev` (via `apt` / `dnf` / `pacman`) |

---

## Build Commands

**Windows:**
```powershell
cd go
go build -o LedgerTimer.exe .
```

**macOS:**
```bash
cd go
go build -o LedgerTimer .
# Optional: package as a .app bundle
go install fyne.io/fyne/v2/cmd/fyne@latest
fyne package -os darwin -icon ../assets/app_icon.png
```

**Linux:**
```bash
cd go
go build -o LedgerTimer .
# Optional: package as a .tar.gz with desktop integration
go install fyne.io/fyne/v2/cmd/fyne@latest
fyne package -os linux -icon ../assets/app_icon.png
```

> `fyne package` creates platform-native bundles (`.app`, `.exe` with icon, etc.) and is optional — `go build` produces a working binary on all platforms.

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

- Project is a `widget.Select` (dropdown) populated from distinct non-null project names in the DB.
- Description is a `widget.Entry` (optional).
- Clock label is hidden when no timer is running; shown and ticking once started.
- Discard button appears below the clock while a timer is running; hidden otherwise.

### History view (click History in the menu bar)

Replaces the main content via `window.SetContent()`. Shows a scrollable list of all log entries, newest first.

Columns: Date | Start | End | Duration | Description | Project | [Edit] [Delete]

- Edit opens a `dialog.Custom` modal with fields for Date, Start Time, End Time, Description, Project.
- Delete prompts for confirmation (`dialog.ShowConfirm`) before removing the entry.
- A **← Back** button returns to the main timer view.

### Export view (click Export in the menu bar)

Replaces the main content via `window.SetContent()`.

```
  From: [YYYY-MM-DD]   To: [YYYY-MM-DD]

         [ Export to CSV ]
```

- Defaults to first and last day of the current month.
- Only completed entries (with an end time) within the date range are exported.
- A file-save dialog (`dialog.ShowFileSave`) lets the user choose the output path.
- A **← Back** button returns to the main timer view.

### View switching

Implemented by calling `window.SetContent(newContainer)` to swap between the timer, history, and export containers. No navigation stack needed — Back always returns to the timer view.

On macOS the menu bar appears in the system menu bar at the top of the screen. On Windows and Linux it appears inside the window.

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
- Same directory as the executable (resolved via `os.Executable()`).
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
2. Switch button label to "■ Stop".
3. Show clock label and Discard button (via `widget.Refresh` / container rebuild).
4. Launch `time.Ticker` goroutine (1s interval) → update clock label directly (Fyne is goroutine-safe).

**Stop:**
1. Call `db.StopTimer()`.
2. Stop ticker goroutine (close a `done` channel).
3. Clear description field, hide clock and Discard button, switch button back to "▶ Start".
4. If History view is currently visible, refresh it.

**Discard:** `dialog.ShowConfirm` → on Yes: `db.DeleteLog()` → same UI reset as Stop.

**Crash recovery on startup:** Call `GetRunningEntry()` — if a running entry exists, restore running ID and start time, populate fields, start ticking.

**Live field sync:** `OnChanged` handlers on the Description and Project fields call `db.UpdateLog()` immediately (preserving `end_time = nil`) so state survives an unexpected exit.

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

- Any features not present in the Python version.
