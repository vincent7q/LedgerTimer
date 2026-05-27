"""
gui.py — All UI logic for LedgerTimer using CustomTkinter.

Layout:
  Top panel    — Project selector, Description input, Start/Stop button + elapsed clock
  Middle panel — Scrollable log list with Edit / Delete per row
  Bottom panel — Date range pickers + Export to CSV button
"""

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
    hours = delta.total_seconds() / 3600
    return f"{hours:.2f}h"


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


# ── Main Application Window ──────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LedgerTimer")
        self.geometry("900x640")
        self.minsize(800, 500)

        db.init_db()

        self._running_id: int | None = None
        self._running_start: str | None = None
        self._tick_job = None

        self._build_ui()
        self._restore_running_state()
        self._refresh_log_list()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_top_panel()
        self._build_middle_panel()
        self._build_bottom_panel()

    def _build_top_panel(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=1)

        # Row 0: Labels
        ctk.CTkLabel(frame, text="Project:").grid(row=0, column=0, padx=(10, 16), pady=(10, 2), sticky="w")
        ctk.CTkLabel(frame, text="Description:").grid(row=0, column=1, padx=(0, 0), pady=(10, 2), sticky="w")

        # Row 1: Inputs
        self._proj_var = tk.StringVar()
        self._proj_combo = ctk.CTkComboBox(frame, variable=self._proj_var, values=[], width=154)
        self._proj_combo.grid(row=1, column=0, padx=(10, 16), pady=(0, 10), sticky="w")

        self._desc_var = tk.StringVar()
        ctk.CTkEntry(frame, textvariable=self._desc_var, placeholder_text="(optional)").grid(
            row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="ew"
        )

        # Persist description/project changes to the running entry in real time
        self._proj_var.trace_add("write", self._on_top_field_change)
        self._desc_var.trace_add("write", self._on_top_field_change)

        # Row 2: Button + clock (left-aligned)
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(4, 10), padx=10, sticky="w")

        self._timer_btn = ctk.CTkButton(
            btn_frame, text="▶  Start", width=140, height=40,
            fg_color="#2e7d32", hover_color="#1b5e20",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._toggle_timer,
        )
        self._timer_btn.pack(side="left")

        self._clock_label = ctk.CTkLabel(
            btn_frame, text="", font=ctk.CTkFont(size=18, weight="bold"), width=120
        )
        self._clock_label.pack(side="left", padx=20)

    def _build_middle_panel(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, padx=12, pady=4, sticky="nsew")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Column minimum widths (px) — same values applied to both header and scroll frame
        # so columns stay aligned despite the scrollbar offset in CTkScrollableFrame.
        col_minsizes = [100, 62, 62, 82, 140, 100, 58, 58]

        # Header row — padx right offset (~20 px) compensates for the scrollbar width
        header_frame = ctk.CTkFrame(frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=(4, 22), pady=(6, 0))
        for i, (h, w, ms) in enumerate(zip(COL_HEADERS, COL_WEIGHTS, col_minsizes)):
            header_frame.grid_columnconfigure(i, weight=w, minsize=ms)
            ctk.CTkLabel(
                header_frame, text=h,
                font=ctk.CTkFont(weight="bold"),
                anchor="w",
            ).grid(row=0, column=i, sticky="ew", padx=4)

        # Scrollable list
        self._scroll_frame = ctk.CTkScrollableFrame(frame)
        self._scroll_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2, 6))
        for i, (w, ms) in enumerate(zip(COL_WEIGHTS, col_minsizes)):
            self._scroll_frame.grid_columnconfigure(i, weight=w, minsize=ms)

    def _build_bottom_panel(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=2, column=0, padx=12, pady=(4, 12), sticky="ew")

        ctk.CTkLabel(frame, text="From:").pack(side="left", padx=(10, 4), pady=10)
        self._from_var = tk.StringVar(value=_first_of_month())
        ctk.CTkEntry(frame, textvariable=self._from_var, width=110).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(frame, text="To:").pack(side="left", padx=(0, 4))
        self._to_var = tk.StringVar(value=_last_of_month())
        ctk.CTkEntry(frame, textvariable=self._to_var, width=110).pack(side="left", padx=(0, 16))

        ctk.CTkButton(frame, text="Export to CSV", command=self._export_csv).pack(side="left", pady=10)

        ctk.CTkLabel(
            frame, text=f"v{__version__}",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack(side="right", padx=(0, 12), pady=10)

    # ── Timer Logic ──────────────────────────────────────────────────────────

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

    def _set_button_idle(self):
        self._timer_btn.configure(
            text="▶  Start", fg_color="#2e7d32", hover_color="#1b5e20"
        )
        self._clock_label.configure(text="")

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

    # ── Log List ─────────────────────────────────────────────────────────────

    def _refresh_log_list(self):
        # Clear existing rows
        for widget in self._scroll_frame.winfo_children():
            widget.destroy()

        # Refresh project dropdown
        projects = db.get_distinct_projects()
        self._proj_combo.configure(values=projects)

        rows = db.get_all_logs()
        for r_idx, row in enumerate(rows):
            # Theme-aware alternating row colours: (light-mode, dark-mode)
            bg = ("#e8e8e8", "#2b2b2b") if r_idx % 2 == 0 else ("#f5f5f5", "#333333")
            self._add_log_row(r_idx, dict(row), bg)

    def _add_log_row(self, r_idx: int, row: dict, bg: str):
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

        for c_idx, (val, w) in enumerate(zip(values, COL_WEIGHTS[:6])):
            lbl = ctk.CTkLabel(
                self._scroll_frame, text=val, anchor="w",
                fg_color=bg, corner_radius=0,
                text_color=("black", "white"),
            )
            lbl.grid(row=r_idx, column=c_idx, sticky="ew", padx=2, pady=1, ipady=4)

        # Edit button
        edit_btn = ctk.CTkButton(
            self._scroll_frame, text="Edit", width=50, height=26,
            command=lambda r=row: self._open_edit(r),
        )
        edit_btn.grid(row=r_idx, column=6, padx=2, pady=1)

        # Delete button
        del_btn = ctk.CTkButton(
            self._scroll_frame, text="Del", width=50, height=26,
            fg_color="#c62828", hover_color="#b71c1c",
            command=lambda r=row: self._delete_entry(r),
        )
        del_btn.grid(row=r_idx, column=7, padx=2, pady=1)

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

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_csv(self):
        from_date = self._from_var.get().strip()
        to_date = self._to_var.get().strip()

        # Validate dates
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
            return  # user cancelled

        rows = db.get_logs_for_export(from_date, to_date)
        count = exp.export_to_csv(rows, filepath)
        messagebox.showinfo("Export Complete", f"Exported {count} entries to:\n{filepath}", parent=self)
