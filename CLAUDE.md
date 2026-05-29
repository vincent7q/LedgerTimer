# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Commands

**Run the app:**
```bash
python -m ledgertimer
```

**Run tests:**
```bash
pytest
```

**Run a single test file:**
```bash
pytest tests/test_database.py
pytest tests/test_export.py
```

**Run a single test:**
```bash
pytest tests/test_database.py::test_stop_timer_clears_running
```

**Build Windows executable:**
```bash
python -m PyInstaller LedgerTimer.spec --noconfirm
```
Always use `LedgerTimer.spec` — never raw `pyinstaller --onefile` (it regenerates the spec and loses icon settings). Output lands at `dist/LedgerTimer.exe`.

**Regenerate app icon (optional):**
```bash
python ledgertimer/ico_generator.py
```

## Architecture

Three modules with strict separation of concerns:

- **`ledgertimer/database.py`** — SQLite data layer. All DB access goes here. Uses `sqlite3.Row` for dict-style row access. `DB_PATH` switches automatically: next to the `.exe` when frozen by PyInstaller, inside `ledgertimer/` during development. `init_db()` is called once at app startup from `App.__init__`.

- **`ledgertimer/gui.py`** — All UI logic. `App` (subclass of `ctk.CTk`) owns timer state (`_running_id`, `_running_start`, `_tick_job`) and orchestrates the three panels. `EditModal` (subclass of `ctk.CTkToplevel`) is a self-contained modal for editing log entries. The GUI writes description/project changes live to the DB on every keystroke via `_on_top_field_change` so state survives crashes.

- **`ledgertimer/export.py`** — CSV export. Converts `sqlite3.Row` sequences to a CSV with duration in decimal hours. No GUI or DB imports.

**Entry points:** `ledgertimer/__main__.py` (for `python -m ledgertimer`) and `run.py` (for PyInstaller). Both just call `App().mainloop()`.

## Key Conventions

- **CustomTkinter only** — use `CTkButton`, `CTkEntry`, `CTkFrame`, etc. Never raw `tkinter` widgets in the UI (except `tk.StringVar` / `tk.filedialog` / `tk.messagebox`, which have no CTk equivalents).
- **Datetime format** — `%Y-%m-%dT%H:%M:%S` (`DT_FMT`) is used for all DB storage. Display uses `%H:%M` (`DISPLAY_TIME_FMT`). Date filters use `%Y-%m-%d` (`DATE_FMT`).
- **Tests use monkeypatching** — `test_database.py` redirects `database.DB_PATH` to a `tmp_path` fixture so tests never touch the real DB. `test_export.py` uses a minimal `_Row(dict)` stub instead of real `sqlite3.Row` objects.
- **Version** is defined in `ledgertimer/__init__.py` as `__version__` and displayed in the bottom panel.
