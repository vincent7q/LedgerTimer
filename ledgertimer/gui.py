"""
gui.py — All UI logic for LedgerTimer using CustomTkinter.

Layout:
  Top panel   — Project selector, Description input, Start/Stop button + elapsed clock
  History tab — Scrollable log list with Edit / Delete per row
  Export tab  — Date range pickers + Export to CSV button
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, date, timedelta
import customtkinter as ctk

from . import database as db
from . import export as exp
from . import __version__

# ── appearance ──────────────────────────────────────────────────────────────
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

DATE_FMT = "%Y-%m-%d"
DT_FMT = "%Y-%m-%dT%H:%M:%S"
DISPLAY_TIME_FMT = "%H:%M"

COL_WEIGHTS = [3, 2, 2, 2, 6, 3, 1, 1]  # Date Start End Dur Desc Proj Edit Del
COL_HEADERS = ["Date", "Start", "End", "Duration", "Description", "Project", "", ""]


# ── helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now().strftime(DT_FMT)


def _elapsed_str(start_iso: str) -> str:
    delta = datetime.now() - datetime.strptime(start_iso, DT_FMT)
    total = int(delta.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _duration_label(start_iso: str, end_iso: str) -> str:
    delta = datetime.strptime(end_iso, DT_FMT) - datetime.strptime(start_iso, DT_FMT)
    total_minutes = int(delta.total_seconds() / 60)
    h, m = divmod(total_minutes, 60)
    return f"{h}h {m:02d}m"


def _first_of_month() -> str:
    today = date.today()
    return today.replace(day=1).strftime(DATE_FMT)


def _last_of_month() -> str:
    today = date.today()
    # go to first of next month then back one day
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return last.strftime(DATE_FMT)


# ── Edit Modal ───────────────────────────────────────────────────────────────

class EditModal(ctk.CTkToplevel):
    def __init__(self, parent, row: dict, on_save_callback):
        super().__init__(parent)
        self.title("Edit Entry")
        self.resizable(False, False)
        self.grab_set()  # modal

        self._row = row
        self._on_save = on_save_callback

        pad = {"padx": 10, "pady": 6}

        # Date
        ctk.CTkLabel(self, text="Date (YYYY-MM-DD)").grid(row=0, column=0, sticky="w", **pad)
        self._date_entry = ctk.CTkEntry(self, width=150)
        self._date_entry.insert(0, datetime.strptime(row["start_time"], DT_FMT).strftime(DATE_FMT))
        self._date_entry.grid(row=0, column=1, **pad)

        # Start time
        ctk.CTkLabel(self, text="Start Time (HH:MM)").grid(row=1, column=0, sticky="w", **pad)
        self._start_entry = ctk.CTkEntry(self, width=150)
        self._start_entry.insert(0, datetime.strptime(row["start_time"], DT_FMT).strftime(DISPLAY_TIME_FMT))
        self._start_entry.grid(row=1, column=1, **pad)

        # End time
        ctk.CTkLabel(self, text="End Time (HH:MM)").grid(row=2, column=0, sticky="w", **pad)
        end_val = ""
        if row["end_time"]:
            end_val = datetime.strptime(row["end_time"], DT_FMT).strftime(DISPLAY_TIME_FMT)
        self._end_entry = ctk.CTkEntry(self, width=150, placeholder_text="leave blank if still running")
        self._end_entry.insert(0, end_val)
        self._end_entry.grid(row=2, column=1, **pad)

        # Description
        ctk.CTkLabel(self, text="Description").grid(row=3, column=0, sticky="w", **pad)
        self._desc_entry = ctk.CTkEntry(self, width=300)
        self._desc_entry.insert(0, row["description"] or "")
        self._desc_entry.grid(row=3, column=1, **pad)

        # Project
        ctk.CTkLabel(self, text="Project (optional)").grid(row=4, column=0, sticky="w", **pad)
        self._proj_entry = ctk.CTkEntry(self, width=300)
        self._proj_entry.insert(0, row["project"] or "")
        self._proj_entry.grid(row=4, column=1, **pad)

        # Error label
        self._err_label = ctk.CTkLabel(self, text="", text_color="red")
        self._err_label.grid(row=5, column=0, columnspan=2, **pad)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Save", command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", command=self.destroy).pack(side="left", padx=8)

    def _save(self):
        date_str = self._date_entry.get().strip()
        start_str = self._start_entry.get().strip()
        end_str = self._end_entry.get().strip()
        desc = self._desc_entry.get().strip()
        project = self._proj_entry.get().strip() or None

        # Validate
        try:
            datetime.strptime(date_str, DATE_FMT)
        except ValueError:
            self._err_label.configure(text="Invalid date. Use YYYY-MM-DD.")
            return

        try:
            datetime.strptime(start_str, DISPLAY_TIME_FMT)
        except ValueError:
            self._err_label.configure(text="Invalid start time. Use HH:MM.")
            return

        start_iso = f"{date_str}T{start_str}:00"
        end_iso = None

        if end_str:
            try:
                datetime.strptime(end_str, DISPLAY_TIME_FMT)
            except ValueError:
                self._err_label.configure(text="Invalid end time. Use HH:MM.")
                return
            end_iso = f"{date_str}T{end_str}:00"
            if end_iso <= start_iso:
                self._err_label.configure(text="End time must be after start time.")
                return

        db.update_log(self._row["id"], start_iso, end_iso, desc, project)
        self._on_save()
        self.destroy()


# ── History Window ─────────────────────────────────────────────────────────

class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("History")
        self.geometry("900x520")
        self.minsize(700, 400)
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        col_minsizes = [100, 62, 62, 82, 140, 100, 58, 58]

        header_frame = ctk.CTkFrame(self, fg_color=("gray80", "gray25"))
        header_frame.grid(row=0, column=0, sticky="ew", padx=(4, 22), pady=(6, 0))
        for i, (h, w, ms) in enumerate(zip(COL_HEADERS, COL_WEIGHTS, col_minsizes)):
            header_frame.grid_columnconfigure(i, weight=w, minsize=ms)
            anchor = "center" if i < 4 else "w"
            ctk.CTkLabel(
                header_frame, text=h,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor=anchor,
            ).grid(row=0, column=i, sticky="ew", padx=4, pady=3)

        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2, 4))
        for i, (w, ms) in enumerate(zip(COL_WEIGHTS, col_minsizes)):
            self.scroll_frame.grid_columnconfigure(i, weight=w, minsize=ms)

        self.total_label = ctk.CTkLabel(
            self, text="Total: —",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        )
        self.total_label.grid(row=2, column=0, sticky="w", padx=8, pady=(2, 6))


# ── Export Window ────────────────────────────────────────────────────────────

class ExportWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Export")
        self.resizable(False, False)
        self._build()

    def _build(self):
        pad = {"padx": 14, "pady": 10}

        ctk.CTkLabel(self, text="From:", anchor="w", width=70).grid(
            row=0, column=0, **pad, sticky="w"
        )
        self._from_var = tk.StringVar(value=_first_of_month())
        ctk.CTkEntry(self, textvariable=self._from_var, width=130).grid(
            row=0, column=1, **pad, sticky="w"
        )

        ctk.CTkLabel(self, text="To:", anchor="w", width=70).grid(
            row=1, column=0, **pad, sticky="w"
        )
        self._to_var = tk.StringVar(value=_last_of_month())
        ctk.CTkEntry(self, textvariable=self._to_var, width=130).grid(
            row=1, column=1, **pad, sticky="w"
        )

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, padx=14, pady=(4, 16), sticky="e")
        ctk.CTkButton(btn_frame, text="Export to CSV", command=self._do_export).pack()

    def _do_export(self):
        from_date = self._from_var.get().strip()
        to_date = self._to_var.get().strip()

        try:
            datetime.strptime(from_date, DATE_FMT)
            datetime.strptime(to_date, DATE_FMT)
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter dates in YYYY-MM-DD format.", parent=self)
            return

        if from_date > to_date:
            messagebox.showerror("Invalid Range", "'From' date must be on or before 'To' date.", parent=self)
            return

        default_name = f"LedgerTimer_{from_date[:7].replace('-', '')}.csv"
        filepath = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_name,
            title="Export to CSV",
        )
        if not filepath:
            return

        rows = db.get_logs_for_export(from_date, to_date)
        count = exp.export_to_csv(rows, filepath)
        messagebox.showinfo("Export Complete", f"Exported {count} entries to:\n{filepath}", parent=self)


# ── Main Application Window ──────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LedgerTimer")
        self.geometry("460x210")
        self.minsize(400, 180)
        _base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        _ico = os.path.join(_base, "ledgertimer", "app_icon.ico")
        if not os.path.exists(_ico):
            _ico = os.path.join(os.path.dirname(__file__), "app_icon.ico")
        if os.path.exists(_ico):
            self.iconbitmap(_ico)

        db.init_db()

        self._running_id: int | None = None
        self._running_start: str | None = None
        self._tick_job = None
        self._history_win = None
        self._export_win = None

        self._build_ui()
        self._restore_running_state()
        self._refresh_log_list()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        WIDGET_H = 36
        ENTRY_W = 260

        # ── Menu bar (History / Export at the top) ──
        menubar = tk.Menu(self)
        menubar.add_command(label="History", command=self._open_history)
        menubar.add_command(label="Export",  command=self._open_export)
        self.configure(menu=menubar)

        self.grid_columnconfigure(1, weight=1)

        # Project row
        ctk.CTkLabel(self, text="Project:", width=100, anchor="w").grid(
            row=0, column=0, padx=(20, 8), pady=(20, 8), sticky="w"
        )
        self._proj_var = tk.StringVar()
        self._proj_combo = ctk.CTkComboBox(
            self, variable=self._proj_var, values=[], height=WIDGET_H, width=ENTRY_W
        )
        self._proj_combo.grid(row=0, column=1, padx=(0, 20), pady=(20, 8), sticky="ew")

        # Description row
        ctk.CTkLabel(self, text="Description:", width=100, anchor="w").grid(
            row=1, column=0, padx=(20, 8), pady=(0, 8), sticky="w"
        )
        self._desc_var = tk.StringVar()
        ctk.CTkEntry(
            self, textvariable=self._desc_var,
            placeholder_text="(optional)", height=WIDGET_H, width=ENTRY_W
        ).grid(row=1, column=1, padx=(0, 20), pady=(0, 8), sticky="ew")

        # Persist changes to running entry in real time
        self._proj_var.trace_add("write", self._on_top_field_change)
        self._desc_var.trace_add("write", self._on_top_field_change)

        # Start/Stop button — centered across both columns
        self._timer_btn = ctk.CTkButton(
            self, text="▶  Start", height=WIDGET_H, width=160,
            fg_color="#2e7d32", hover_color="#1b5e20",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_timer,
        )
        self._timer_btn.grid(row=2, column=0, columnspan=2, pady=(4, 8))

        # Clock — hidden until timer is running
        self._clock_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=20, weight="bold")
        )
        self._clock_label.grid(row=3, column=0, columnspan=2, pady=(0, 4))
        self._clock_label.grid_remove()

        # Discard button — hidden until timer is running
        self._cancel_btn = ctk.CTkButton(
            self, text="✕  Discard", height=WIDGET_H, width=160,
            fg_color="#757575", hover_color="#616161",
            font=ctk.CTkFont(size=12),
            command=self._cancel_timer,
        )
        self._cancel_btn.grid(row=4, column=0, columnspan=2, pady=(0, 4))
        self._cancel_btn.grid_remove()

        # Version label — bottom right
        ctk.CTkLabel(
            self, text=f"v{__version__}",
            text_color="gray",
            font=ctk.CTkFont(size=10),
        ).grid(row=5, column=1, padx=(0, 8), pady=(0, 6), sticky="se")

    def _toggle_timer(self):
        if self._running_id is None:
            self._start_timer()
        else:
            self._stop_timer()

    def _start_timer(self):
        desc = self._desc_var.get().strip()
        project = self._proj_var.get().strip() or None
        start_iso = _now_iso()
        row_id = db.start_timer(start_iso, desc, project)
        self._running_id = row_id
        self._running_start = start_iso
        self._set_button_active()
        self._tick()
        self._refresh_log_list()

    def _stop_timer(self):
        end_iso = _now_iso()
        db.stop_timer(self._running_id, end_iso)
        self._running_id = None
        self._running_start = None
        if self._tick_job:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self._desc_var.set("")
        self._set_button_idle()
        self._refresh_log_list()

    def _set_button_active(self):
        self._timer_btn.configure(
            text="■  Stop", fg_color="#c62828", hover_color="#b71c1c"
        )
        self._clock_label.grid()
        self._cancel_btn.grid()

    def _set_button_idle(self):
        self._timer_btn.configure(
            text="▶  Start", fg_color="#2e7d32", hover_color="#1b5e20"
        )
        self._clock_label.configure(text="")
        self._clock_label.grid_remove()
        self._cancel_btn.grid_remove()

    def _cancel_timer(self):
        """Discard the running timer without saving."""
        confirmed = messagebox.askyesno(
            "Discard Timer",
            "Delete this timer entry? The time will not be saved.",
            parent=self,
        )
        if not confirmed:
            return
        db.delete_log(self._running_id)
        self._running_id = None
        self._running_start = None
        if self._tick_job:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self._desc_var.set("")
        self._set_button_idle()
        self._refresh_log_list()

    def _tick(self):
        if self._running_start:
            self._clock_label.configure(text=_elapsed_str(self._running_start))
            self._tick_job = self.after(1000, self._tick)

    def _restore_running_state(self):
        """On startup, resume any previously running timer."""
        row = db.get_running_entry()
        if row:
            self._running_id = row["id"]
            self._running_start = row["start_time"]
            self._desc_var.set(row["description"] or "")
            self._proj_var.set(row["project"] or "")
            self._set_button_active()
            self._tick()

    def _on_top_field_change(self, *_):
        """Write description/project to the running DB entry on every keystroke."""
        if self._running_id is None:
            return
        desc = self._desc_var.get().strip()
        project = self._proj_var.get().strip() or None
        db.update_log(self._running_id, self._running_start, None, desc, project)

    def _open_history(self):
        if self._history_win and self._history_win.winfo_exists():
            self._history_win.lift()
            self._history_win.focus_force()
            return
        self._history_win = HistoryWindow(self)
        self._refresh_log_list()
        self.after(150, lambda: (
            self._history_win.lift(),
            self._history_win.focus_force(),
        ))

    def _open_export(self):
        if self._export_win and self._export_win.winfo_exists():
            self._export_win.lift()
            self._export_win.focus_force()
            return
        self._export_win = ExportWindow(self)
        self.after(150, lambda: (
            self._export_win.lift(),
            self._export_win.focus_force(),
        ))
    # ── Log List ─────────────────────────────────────────────────────────────

    def _refresh_log_list(self):
        # Always refresh project dropdown on main window
        projects = db.get_distinct_projects()
        self._proj_combo.configure(values=projects)

        # Only populate log table if History window is open
        if not (self._history_win and self._history_win.winfo_exists()):
            return

        hw = self._history_win
        for widget in hw.scroll_frame.winfo_children():
            widget.destroy()

        rows = db.get_all_logs()

        total_minutes = 0
        for row in rows:
            if row["end_time"]:
                delta = datetime.strptime(row["end_time"], DT_FMT) - datetime.strptime(row["start_time"], DT_FMT)
                total_minutes += int(delta.total_seconds() / 60)
        th, tm = divmod(total_minutes, 60)
        hw.total_label.configure(text=f"Total: {th}h {tm:02d}m")

        for r_idx, row in enumerate(rows):
            bg = ("#e8e8e8", "#2b2b2b") if r_idx % 2 == 0 else ("#f5f5f5", "#333333")
            self._add_log_row(hw.scroll_frame, r_idx, dict(row), bg)

    def _add_log_row(self, scroll_frame, r_idx: int, row: dict, bg: str):
        start_dt = datetime.strptime(row["start_time"], DT_FMT)
        date_str = start_dt.strftime(DATE_FMT)
        start_str = start_dt.strftime(DISPLAY_TIME_FMT)

        if row["end_time"]:
            end_dt = datetime.strptime(row["end_time"], DT_FMT)
            end_str = end_dt.strftime(DISPLAY_TIME_FMT)
            dur_str = _duration_label(row["start_time"], row["end_time"])
        else:
            end_str = "──"
            dur_str = "(running)"

        values = [
            date_str,
            start_str,
            end_str,
            dur_str,
            row["description"] or "",
            row["project"] or "",
        ]

        # cols 0-3: centered (date/time); cols 4-5: left-aligned (text)
        anchors = ["center", "center", "center", "center", "w", "w"]
        HOVER_BG = ("#cce3ff", "#1a3a5c")

        row_labels = []
        for c_idx, (val, anchor) in enumerate(zip(values, anchors)):
            lbl = ctk.CTkLabel(
                scroll_frame, text=val, anchor=anchor,
                fg_color=bg, corner_radius=0,
                text_color=("black", "white"),
            )
            lbl.grid(row=r_idx, column=c_idx, sticky="ew", padx=2, pady=1, ipady=3)
            row_labels.append(lbl)

        def _on_enter(event, labels=row_labels):
            for lbl in labels:
                lbl.configure(fg_color=HOVER_BG)

        def _on_leave(event, labels=row_labels, orig=bg):
            for lbl in labels:
                lbl.configure(fg_color=orig)

        for lbl in row_labels:
            lbl.bind("<Enter>", _on_enter)
            lbl.bind("<Leave>", _on_leave)
            lbl.bind("<Double-Button-1>", lambda e, r=row: self._open_edit(r))

        # Edit button
        edit_btn = ctk.CTkButton(
            scroll_frame, text="Edit", width=50, height=24,
            command=lambda r=row: self._open_edit(r),
        )
        edit_btn.grid(row=r_idx, column=6, padx=2, pady=0)

        # Delete button
        del_btn = ctk.CTkButton(
            scroll_frame, text="Del", width=50, height=24,
            fg_color="#c62828", hover_color="#b71c1c",
            command=lambda r=row: self._delete_entry(r),
        )
        del_btn.grid(row=r_idx, column=7, padx=2, pady=0)

    def _open_edit(self, row: dict):
        EditModal(self, row, on_save_callback=self._refresh_log_list)

    def _delete_entry(self, row: dict):
        confirmed = messagebox.askyesno(
            "Delete Entry",
            "Delete this entry? This cannot be undone.",
            parent=self,
        )
        if not confirmed:
            return
        # If deleting the running timer, reset UI state
        if row["id"] == self._running_id:
            self._running_id = None
            self._running_start = None
            if self._tick_job:
                self.after_cancel(self._tick_job)
                self._tick_job = None
            self._set_button_idle()
        db.delete_log(row["id"])
        self._refresh_log_list()
