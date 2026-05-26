# LedgerTimer — Project Specification v1.0

## 1. Overview

A Python desktop time-tracking app for freelancers and contractors. Log billable sessions in real-time or retroactively. Export monthly billing summaries to CSV. Local-only — no network or cloud required.

---

## 2. Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| GUI | `customtkinter` (all widgets must be CTk variants) |
| Storage | `sqlite3` (built-in) |
| Export | `csv` (built-in) |
| Packaging | `PyInstaller` (future) |

---

## 3. File Structure

```
LedgerTimer/
├── main.py          # Entry point — creates App, launches mainloop
├── gui.py           # All UI logic (CTk windows, panels, modals)
├── database.py      # All SQLite read/write operations
├── export.py        # CSV export logic
├── requirements.txt # Python dependencies
└── ledger.db        # Auto-created on first run (gitignored)
```

---

## 4. Database Schema

`database.py` auto-creates tables on first boot if they don't exist.

### Table: `logs`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `start_time` | TEXT NOT NULL | ISO 8601: `YYYY-MM-DDTHH:MM:SS` |
| `end_time` | TEXT | NULL = timer still running |
| `description` | TEXT | Empty string allowed |
| `project` | TEXT | NULL if not tagged (optional field) |

**Rules:**
- At most one row may have `end_time = NULL` at any time (the active timer).
- `start_time` is written to the DB the moment the user clicks **Start** — this enables resume-on-reopen.

---

## 5. UI Layout

All panels are inside a single `CTkFrame` root window (resizable).

### 5.1 Top Panel — Timer Control

```
┌─────────────────────────────────────────────────────────┐
│  Project (optional):  [Dropdown / type-in combobox   ▼] │
│  Description:         [                               ] │
│                                                         │
│              [ ▶  START  ]     00:00:00                 │
└─────────────────────────────────────────────────────────┘
```

- **Project dropdown** (`CTkComboBox`): populated from distinct `project` values in DB. User may type a new name. If left blank → stored as `NULL`.
- **Description field** (`CTkEntry`): plain text, may be empty.
- **Start/Stop button** (`CTkButton`):
  - Idle state: green "▶ Start"
  - Active state: red "■ Stop"
- **Elapsed clock** (`CTkLabel`): shows `HH:MM:SS`, updated every second via `root.after(1000, ...)`. Only visible while timer is running.

### 5.2 Middle Panel — Log List

```
┌──────────────────────────────────────────────────────────────────┐
│  Date        Start   End     Duration  Description  Project      │
│ ──────────────────────────────────────────────────────────────── │
│  2026-05-26  09:00   17:30   8.50h     Meeting...   ClientA      │
│  2026-05-26  18:00   ──      (running) Code review               │
│  ...                                       [Edit]  [Del] per row │
└──────────────────────────────────────────────────────────────────┘
```

- Implemented as a `CTkScrollableFrame` with a grid of `CTkLabel` and `CTkButton` per row.
- All historical logs shown (no date filter in this view).
- Rows sorted by `start_time DESC` (most recent first).
- The currently-running entry shows `──` for End Time and `(running)` for Duration.
- **Edit button** per row → opens Edit Modal (§5.3).
- **Delete button** per row → shows confirmation dialog before deleting.

### 5.3 Edit Modal (`CTkToplevel`)

Fields (pre-filled with current values):

| Field | Widget | Notes |
|---|---|---|
| Date | `CTkEntry` | `YYYY-MM-DD` |
| Start Time | `CTkEntry` | `HH:MM` |
| End Time | `CTkEntry` | `HH:MM` — may be blank if entry is still running |
| Description | `CTkEntry` | May be empty |
| Project | `CTkEntry` | May be empty |

Buttons: **Save** | **Cancel**

**Validation on Save:**
- Date must be a valid calendar date.
- Start Time must be valid `HH:MM`.
- If End Time provided: must be valid `HH:MM` and strictly after Start Time (same-day assumption).
- Show inline error label on failure — do not close modal.

### 5.4 Bottom Panel — Export

```
┌──────────────────────────────────────────────────────┐
│  From: [2026-05-01]  To: [2026-05-31]                │
│                          [ Export to CSV ]           │
└──────────────────────────────────────────────────────┘
```

- **From / To** (`CTkEntry`): defaults to first and last day of current month.
- **Export button**: opens OS file-save dialog, saves CSV.
- Entries with no `end_time` (still running) are **excluded** from export.

---

## 6. CSV Export Format

Filename suggestion: `LedgerTimer_YYYYMM.csv` (pre-filled in save dialog).

```csv
Date,Start Time,End Time,Duration,Description,Project
2026-05-26,09:00,17:30,8.50,Client meeting,ClientA
2026-05-26,18:00,19:45,1.75,Code review,
```

| Column | Format | Notes |
|---|---|---|
| Date | `YYYY-MM-DD` | |
| Start Time | `HH:MM` | 24-hour |
| End Time | `HH:MM` | 24-hour |
| Duration | Decimal hours, 2 d.p. | e.g. `1.75` |
| Description | Plain text | Empty string if blank |
| Project | Plain text | Empty string if not tagged |

**Duration formula:** `(end_datetime - start_datetime).total_seconds() / 3600`, rounded to 2 decimal places.

---

## 7. Timer Persistence (App Close / Reopen)

| Event | Action |
|---|---|
| User clicks **Start** | `INSERT` row with `start_time = now`, `end_time = NULL` |
| User clicks **Stop** | `UPDATE` row, set `end_time = now` |
| App launches | `SELECT` row `WHERE end_time IS NULL` |
| Running row found | Restore UI to active state; restart elapsed clock from `now - start_time` |

---

## 8. Delete Behaviour

1. User clicks **Del** on a row.
2. Confirmation dialog: *"Delete this entry? This cannot be undone."* — **Confirm / Cancel**
3. On Confirm: `DELETE FROM logs WHERE id = ?`
4. Refresh log list.
5. If the deleted entry was the active running timer → reset UI to idle state.

---

## 9. Design Decisions (Q&A Summary)

| Question | Decision |
|---|---|
| Client/Project tagging | Optional field — not required to start a timer |
| Duration format | Decimal hours (e.g. `1.75`) |
| Time format | 24-hour (`HH:MM`) |
| Concurrent timers | One at a time only |
| App close with running timer | Resume on reopen (start_time persisted in DB) |
| Delete entries | Yes, with confirmation dialog |
| Log list scope | All logs, scrollable — no date filter in main view |

---

## 10. Out of Scope (MVP)

- Multiple concurrent timers
- Date-range filtering within the log list
- Dark/light mode toggle (uses system default)
- Cloud sync or backup
- Excel `.xlsx` export (CSV only)
- Time rounding (e.g. nearest 15 min)
- Billable rate / invoice calculation

---

## 11. Suggested Future Enhancements

- Idle detection / auto-pause
- Weekly/daily summary view
- Billable rate field for automatic invoice totals
- `.xlsx` export with formatting
- Filter log list by project or date range
