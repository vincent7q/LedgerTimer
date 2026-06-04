"""
gui.py — All UI logic for LedgerTimer using CustomTkinter (v2.0).

New in v2.0:
  F1  Pause / Resume timer
  F2  Add past entry manually
  F3  Filter bar in History (project, date range, keyword)
  U1  System tray (minimize-to-tray, tray tooltip shows elapsed)
  U7  Resizable columns in History (drag column header)
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, date, timedelta
import customtkinter as ctk

from . import database as db
from . import export as exp
from . import __version__

# Optional tray support — gracefully absent if pystray/Pillow not installed
try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False

# ── appearance ──────────────────────────────────────────────────────────────
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

DATE_FMT = "%Y-%m-%d"
DT_FMT = "%Y-%m-%dT%H:%M:%S"
DISPLAY_TIME_FMT = "%H:%M"

COL_HEADERS  = ["Date", "Start", "End", "Duration", "Description", "Project", "", ""]
COL_WEIGHTS  = [3, 2, 2, 2, 6, 3, 1, 1]
COL_MINSIZES = [100, 62, 62, 82, 140, 100, 58, 58]


# ── helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now().strftime(DT_FMT)


def _elapsed_str(start_iso: str, paused_seconds: int = 0) -> str:
    """Return HH:MM:SS elapsed, subtracting accumulated paused time."""
    delta = datetime.now() - datetime.strptime(start_iso, DT_FMT)
    total = max(0, int(delta.total_seconds()) - paused_seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _duration_label(start_iso: str, end_iso: str, paused_seconds: int = 0) -> str:
    """Return human-readable duration like '2h 05m', subtracting paused time."""
    delta = datetime.strptime(end_iso, DT_FMT) - datetime.strptime(start_iso, DT_FMT)
    total_minutes = max(0, int(delta.total_seconds() - paused_seconds) // 60)
    h, m = divmod(total_minutes, 60)
    return f"{h}h {m:02d}m"


def _first_of_month() -> str:
    today = date.today()
    return today.replace(day=1).strftime(DATE_FMT)


def _last_of_month() -> str:
    today = date.today()
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return last.strftime(DATE_FMT)


def _make_tray_image(running: bool = False) -> "Image.Image":
    """Draw a minimal clock icon for the system tray."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg = (46, 125, 50, 255) if running else (90, 90, 90, 255)
    draw.ellipse([4, 4, size - 4, size - 4], fill=bg)
    cx, cy = size // 2, size // 2
    draw.line([cx, cy, cx, cy - 18], fill="white", width=3)   # minute hand
    draw.line([cx, cy, cx + 12, cy + 8], fill="white", width=3)  # hour hand
    return img


# ── Edit Modal ───────────────────────────────────────────────────────────────

class EditModal(ctk.CTkToplevel):
    def __init__(self, parent, row: dict, on_save_callback):
        super().__init__(parent)
        self.title("Edit Entry")
        self.resizable(False, False)
        self.grab_set()

        self._row = row
        self._on_save = on_save_callback

        pad = {"padx": 10, "pady": 6}

        ctk.CTkLabel(self, text="Date (YYYY-MM-DD)").grid(row=0, column=0, sticky="w", **pad)
        self._date_entry = ctk.CTkEntry(self, width=150)
        self._date_entry.insert(0, datetime.strptime(row["start_time"], DT_FMT).strftime(DATE_FMT))
        self._date_entry.grid(row=0, column=1, **pad)

        ctk.CTkLabel(self, text="Start Time (HH:MM)").grid(row=1, column=0, sticky="w", **pad)
        self._start_entry = ctk.CTkEntry(self, width=150)
        self._start_entry.insert(0, datetime.strptime(row["start_time"], DT_FMT).strftime(DISPLAY_TIME_FMT))
        self._start_entry.grid(row=1, column=1, **pad)

        ctk.CTkLabel(self, text="End Time (HH:MM)").grid(row=2, column=0, sticky="w", **pad)
        end_val = ""
        if row["end_time"]:
            end_val = datetime.strptime(row["end_time"], DT_FMT).strftime(DISPLAY_TIME_FMT)
        self._end_entry = ctk.CTkEntry(self, width=150, placeholder_text="leave blank if still running")
        self._end_entry.insert(0, end_val)
        self._end_entry.grid(row=2, column=1, **pad)

        ctk.CTkLabel(self, text="Description").grid(row=3, column=0, sticky="w", **pad)
        self._desc_entry = ctk.CTkEntry(self, width=300)
        self._desc_entry.insert(0, row["description"] or "")
        self._desc_entry.grid(row=3, column=1, **pad)

        ctk.CTkLabel(self, text="Project (optional)").grid(row=4, column=0, sticky="w", **pad)
        self._proj_entry = ctk.CTkEntry(self, width=300)
        self._proj_entry.insert(0, row["project"] or "")
        self._proj_entry.grid(row=4, column=1, **pad)

        self._err_label = ctk.CTkLabel(self, text="", text_color="red")
        self._err_label.grid(row=5, column=0, columnspan=2, **pad)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Save", command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", command=self.destroy).pack(side="left", padx=8)

    def _save(self):
        date_str  = self._date_entry.get().strip()
        start_str = self._start_entry.get().strip()
        end_str   = self._end_entry.get().strip()
        desc      = self._desc_entry.get().strip()
        project   = self._proj_entry.get().strip() or None

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


# ── Add Entry Modal (F2) ──────────────────────────────────────────────────────

class AddEntryModal(ctk.CTkToplevel):
    """Manually log a completed past session without running the timer."""

    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.title("Add Past Entry")
        self.resizable(False, False)
        self.grab_set()

        self._on_save = on_save_callback
        pad = {"padx": 10, "pady": 6}

        ctk.CTkLabel(self, text="Date (YYYY-MM-DD)").grid(row=0, column=0, sticky="w", **pad)
        self._date_entry = ctk.CTkEntry(self, width=150)
        self._date_entry.insert(0, date.today().strftime(DATE_FMT))
        self._date_entry.grid(row=0, column=1, **pad)

        ctk.CTkLabel(self, text="Start Time (HH:MM)").grid(row=1, column=0, sticky="w", **pad)
        self._start_entry = ctk.CTkEntry(self, width=150, placeholder_text="09:00")
        self._start_entry.grid(row=1, column=1, **pad)

        ctk.CTkLabel(self, text="End Time (HH:MM)").grid(row=2, column=0, sticky="w", **pad)
        self._end_entry = ctk.CTkEntry(self, width=150, placeholder_text="10:00")
        self._end_entry.grid(row=2, column=1, **pad)

        ctk.CTkLabel(self, text="Description").grid(row=3, column=0, sticky="w", **pad)
        self._desc_entry = ctk.CTkEntry(self, width=300)
        self._desc_entry.grid(row=3, column=1, **pad)

        ctk.CTkLabel(self, text="Project (optional)").grid(row=4, column=0, sticky="w", **pad)
        self._proj_entry = ctk.CTkEntry(self, width=300)
        self._proj_entry.grid(row=4, column=1, **pad)

        self._err_label = ctk.CTkLabel(self, text="", text_color="red")
        self._err_label.grid(row=5, column=0, columnspan=2, **pad)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_frame, text="Add", command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", command=self.destroy).pack(side="left", padx=8)

    def _save(self):
        date_str  = self._date_entry.get().strip()
        start_str = self._start_entry.get().strip()
        end_str   = self._end_entry.get().strip()
        desc      = self._desc_entry.get().strip()
        project   = self._proj_entry.get().strip() or None

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

        if not end_str:
            self._err_label.configure(text="End time is required for past entries.")
            return

        try:
            datetime.strptime(end_str, DISPLAY_TIME_FMT)
        except ValueError:
            self._err_label.configure(text="Invalid end time. Use HH:MM.")
            return

        start_iso = f"{date_str}T{start_str}:00"
        end_iso   = f"{date_str}T{end_str}:00"
        if end_iso <= start_iso:
            self._err_label.configure(text="End time must be after start time.")
            return

        db.insert_log(start_iso, end_iso, desc, project)
        self._on_save()
        self.destroy()


# ── History Window (F3 filter bar + U7 resizable columns) ───────────────────

class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("History")
        self.geometry("940x580")
        self.minsize(720, 430)

        # Per-column pixel widths — initialised from defaults, mutated on drag
        self._col_widths: list[int] = list(COL_MINSIZES)
        self._resize_col: int | None = None
        self._resize_start_x: int = 0
        self._resize_start_w: int = 0

        # Set by App after construction so Filter/Clear can trigger a refresh
        self._filter_callback = None

        self._build()

    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── row 0: Filter bar ────────────────────────────────────────────────
        ff = ctk.CTkFrame(self, fg_color=("gray90", "gray20"))
        ff.grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 2))

        ctk.CTkLabel(ff, text="Project:", width=55).grid(row=0, column=0, padx=(8, 2), pady=4, sticky="w")
        self._filter_proj_var = tk.StringVar()
        self._filter_proj_combo = ctk.CTkComboBox(
            ff, variable=self._filter_proj_var,
            values=[""] + db.get_distinct_projects(),
            width=130, height=28,
        )
        self._filter_proj_combo.grid(row=0, column=1, padx=(0, 10), pady=4, sticky="w")

        ctk.CTkLabel(ff, text="From:", width=40).grid(row=0, column=2, padx=(0, 2), pady=4, sticky="w")
        self._filter_from_var = tk.StringVar()
        ctk.CTkEntry(ff, textvariable=self._filter_from_var,
                     width=100, height=28, placeholder_text="YYYY-MM-DD"
                     ).grid(row=0, column=3, padx=(0, 10), pady=4, sticky="w")

        ctk.CTkLabel(ff, text="To:", width=25).grid(row=0, column=4, padx=(0, 2), pady=4, sticky="w")
        self._filter_to_var = tk.StringVar()
        ctk.CTkEntry(ff, textvariable=self._filter_to_var,
                     width=100, height=28, placeholder_text="YYYY-MM-DD"
                     ).grid(row=0, column=5, padx=(0, 10), pady=4, sticky="w")

        ctk.CTkLabel(ff, text="Search:", width=50).grid(row=0, column=6, padx=(0, 2), pady=4, sticky="w")
        self._filter_kw_var = tk.StringVar()
        ctk.CTkEntry(ff, textvariable=self._filter_kw_var,
                     width=130, height=28, placeholder_text="keyword"
                     ).grid(row=0, column=7, padx=(0, 10), pady=4, sticky="w")

        ctk.CTkButton(ff, text="Filter", width=70, height=28,
                      command=self._on_filter
                      ).grid(row=0, column=8, padx=(0, 4), pady=4)
        ctk.CTkButton(ff, text="Clear", width=60, height=28,
                      fg_color="gray", hover_color="#616161",
                      command=self._on_clear_filter
                      ).grid(row=0, column=9, padx=(0, 8), pady=4)

        # ── row 1: Column headers ────────────────────────────────────────────
        self._header_frame = ctk.CTkFrame(self, fg_color=("gray80", "gray25"))
        self._header_frame.grid(row=1, column=0, sticky="ew", padx=(4, 22), pady=(2, 0))
        self._header_labels: list[ctk.CTkLabel] = []

        for i, (h, w, ms) in enumerate(zip(COL_HEADERS, COL_WEIGHTS, self._col_widths)):
            self._header_frame.grid_columnconfigure(i, weight=w, minsize=ms)
            anchor = "center" if i < 4 else "w"
            cursor = "sb_h_double_arrow" if i < 6 else ""
            lbl = ctk.CTkLabel(
                self._header_frame, text=h,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor=anchor, cursor=cursor,
            )
            lbl.grid(row=0, column=i, sticky="ew", padx=4, pady=3)
            self._header_labels.append(lbl)
            if i < 6:
                lbl.bind("<ButtonPress-1>",   lambda e, col=i: self._resize_press(e, col))
                lbl.bind("<B1-Motion>",       lambda e, col=i: self._resize_drag(e, col))
                lbl.bind("<ButtonRelease-1>", self._resize_release)

        # ── row 2: Scrollable rows ───────────────────────────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=(2, 4))
        for i, (w, ms) in enumerate(zip(COL_WEIGHTS, self._col_widths)):
            self.scroll_frame.grid_columnconfigure(i, weight=w, minsize=ms)

        # ── row 3: Total ─────────────────────────────────────────────────────
        self.total_label = ctk.CTkLabel(
            self, text="Total: —",
            text_color="gray", font=ctk.CTkFont(size=11),
        )
        self.total_label.grid(row=3, column=0, sticky="w", padx=8, pady=(2, 6))

    def _on_filter(self):
        if self._filter_callback:
            self._filter_callback()

    def _on_clear_filter(self):
        self._filter_proj_var.set("")
        self._filter_from_var.set("")
        self._filter_to_var.set("")
        self._filter_kw_var.set("")
        if self._filter_callback:
            self._filter_callback()

    # ── Column resize (U7) ───────────────────────────────────────────────────

    def _resize_press(self, event, col: int):
        self._resize_col = col
        self._resize_start_x = event.x_root
        self._resize_start_w = self._col_widths[col]

    def _resize_drag(self, event, col: int):
        if self._resize_col != col:
            return
        dx = event.x_root - self._resize_start_x
        self._col_widths[col] = max(40, self._resize_start_w + dx)
        self._apply_col_widths()

    def _resize_release(self, event):
        self._resize_col = None

    def _apply_col_widths(self):
        for i, w in enumerate(self._col_widths):
            self._header_frame.grid_columnconfigure(i, weight=0, minsize=w)
            self.scroll_frame.grid_columnconfigure(i, weight=0, minsize=w)


# ── Export Window ─────────────────────────────────────────────────────────────

class ExportWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Export")
        self.resizable(False, False)
        self._build()

    def _build(self):
        pad = {"padx": 14, "pady": 10}

        ctk.CTkLabel(self, text="From:", anchor="w", width=70).grid(row=0, column=0, **pad, sticky="w")
        self._from_var = tk.StringVar(value=_first_of_month())
        ctk.CTkEntry(self, textvariable=self._from_var, width=130).grid(row=0, column=1, **pad, sticky="w")

        ctk.CTkLabel(self, text="To:", anchor="w", width=70).grid(row=1, column=0, **pad, sticky="w")
        self._to_var = tk.StringVar(value=_last_of_month())
        ctk.CTkEntry(self, textvariable=self._to_var, width=130).grid(row=1, column=1, **pad, sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, padx=14, pady=(4, 16), sticky="e")
        ctk.CTkButton(btn_frame, text="Export to CSV", command=self._do_export).pack()

    def _do_export(self):
        from_date = self._from_var.get().strip()
        to_date   = self._to_var.get().strip()

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


# ── Main Application Window ───────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LedgerTimer")
        self.geometry("480x250")
        self.minsize(400, 220)

        _base = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(__file__)
        _ico = os.path.join(_base, "ledgertimer", "app_icon.ico")
        if not os.path.exists(_ico):
            _ico = os.path.join(os.path.dirname(__file__), "app_icon.ico")
        if os.path.exists(_ico):
            self.iconbitmap(_ico)

        db.init_db()

        self._running_id: int | None = None
        self._running_start: str | None = None
        self._paused_at: str | None = None     # ISO timestamp of current pause start
        self._paused_seconds: int = 0          # accumulated paused seconds this session
        self._tick_job = None
        self._history_win = None
        self._export_win = None
        self._tray_icon = None

        self._build_ui()
        self._restore_running_state()
        self._refresh_log_list()
        if _TRAY_AVAILABLE:
            self._setup_tray()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        WIDGET_H = 36
        ENTRY_W  = 260

        menubar = tk.Menu(self)
        menubar.add_command(label="History",     command=self._open_history)
        menubar.add_command(label="Export",      command=self._open_export)
        menubar.add_command(label="＋ Add Entry", command=self._open_add_entry)
        self.configure(menu=menubar)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)
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

        self._proj_var.trace_add("write", self._on_top_field_change)
        self._desc_var.trace_add("write", self._on_top_field_change)

        # Start / Stop  +  Pause / Resume — side by side
        _btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        _btn_frame.grid(row=2, column=0, columnspan=2, pady=(4, 2))

        self._timer_btn = ctk.CTkButton(
            _btn_frame, text="▶  Start", height=WIDGET_H, width=140,
            fg_color="#2e7d32", hover_color="#1b5e20",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_timer,
        )
        self._timer_btn.grid(row=0, column=0, padx=(0, 6))

        # Pause / Resume button — hidden until timer is running
        self._pause_btn = ctk.CTkButton(
            _btn_frame, text="⏸  Pause", height=WIDGET_H, width=140,
            fg_color="#e65100", hover_color="#bf360c",
            font=ctk.CTkFont(size=13),
            command=self._toggle_pause,
        )
        self._pause_btn.grid(row=0, column=1, padx=(0, 0))
        self._pause_btn.grid_remove()

        # Elapsed clock — hidden until timer is running
        self._clock_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=32, weight="bold")
        )
        self._clock_label.grid(row=3, column=0, columnspan=2, pady=(0, 2))
        self._clock_label.grid_remove()

        # Version label
        ctk.CTkLabel(
            self, text=f"v{__version__}",
            text_color="gray", font=ctk.CTkFont(size=10),
        ).grid(row=4, column=1, padx=(0, 8), pady=(0, 6), sticky="se")

        if _TRAY_AVAILABLE:
            self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Timer control ─────────────────────────────────────────────────────────

    def _toggle_timer(self):
        if self._running_id is None:
            self._start_timer()
        else:
            self._stop_timer()

    def _start_timer(self):
        desc    = self._desc_var.get().strip()
        project = self._proj_var.get().strip() or None
        start_iso = _now_iso()
        row_id = db.start_timer(start_iso, desc, project)
        self._running_id    = row_id
        self._running_start = start_iso
        self._paused_at     = None
        self._paused_seconds = 0
        self._set_button_active()
        self._tick()
        self._refresh_log_list()
        self._update_tray(running=True)

    def _stop_timer(self):
        # Capture info for the confirmation popup before clearing state
        saved_desc    = self._desc_var.get().strip() or "(no description)"
        saved_project = self._proj_var.get().strip() or "(no project)"
        saved_start   = self._running_start

        # Finalise any active pause so paused_duration is accurate in DB
        if self._paused_at:
            db.resume_timer(self._running_id, _now_iso())
        end_iso = _now_iso()
        db.stop_timer(self._running_id, end_iso)

        duration_str = _duration_label(saved_start, end_iso, self._paused_seconds)

        self._running_id     = None
        self._running_start  = None
        self._paused_at      = None
        self._paused_seconds = 0
        if self._tick_job:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self._desc_var.set("")
        self._set_button_idle()
        self._refresh_log_list()
        self._update_tray(running=False)

        messagebox.showinfo(
            "Task Saved",
            f"Duration:    {duration_str}\n"
            f"Description: {saved_desc}\n"
            f"Project:     {saved_project}",
            parent=self,
        )

    def _toggle_pause(self):
        if self._paused_at is None:
            self._pause_timer()
        else:
            self._resume_timer()

    def _pause_timer(self):
        now = _now_iso()
        self._paused_at = now
        db.pause_timer(self._running_id, now)
        if self._tick_job:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self._set_button_paused()
        self._update_tray(running=False)

    def _resume_timer(self):
        now = _now_iso()
        db.resume_timer(self._running_id, now)
        # Reload paused_duration from DB so it's authoritative
        row = db.get_running_entry()
        self._paused_seconds = int(row["paused_duration"] or 0) if row else self._paused_seconds
        self._paused_at = None
        self._set_button_active()
        self._tick()
        self._update_tray(running=True)

    def _set_button_active(self):
        self._timer_btn.configure(text="■  Stop", fg_color="#c62828", hover_color="#b71c1c")
        self._pause_btn.configure(text="⏸  Pause", fg_color="#e65100", hover_color="#bf360c")
        self._pause_btn.grid()
        self._clock_label.grid()

    def _set_button_paused(self):
        self._pause_btn.configure(text="▶  Resume", fg_color="#1565c0", hover_color="#0d47a1")
        self._clock_label.configure(text="⏸  PAUSED")

    def _set_button_idle(self):
        self._timer_btn.configure(text="▶  Start", fg_color="#2e7d32", hover_color="#1b5e20")
        self._clock_label.configure(text="")
        self._clock_label.grid_remove()
        self._pause_btn.grid_remove()

    def _tick(self):
        if self._running_start and self._paused_at is None:
            elapsed = _elapsed_str(self._running_start, self._paused_seconds)
            self._clock_label.configure(text=elapsed)
            self._update_tray_tooltip(elapsed)
            self._tick_job = self.after(1000, self._tick)

    def _restore_running_state(self):
        """On startup, restore any previously running (or paused) timer."""
        row = db.get_running_entry()
        if row:
            self._running_id     = row["id"]
            self._running_start  = row["start_time"]
            self._paused_seconds = int(row["paused_duration"] or 0)
            self._desc_var.set(row["description"] or "")
            self._proj_var.set(row["project"] or "")
            if row["paused_at"]:
                self._paused_at = row["paused_at"]
                # Show paused UI without starting the tick loop
                self._set_button_active()
                self._set_button_paused()
                self._clock_label.grid()
                self._pause_btn.grid()
                self._cancel_btn.grid()
            else:
                self._paused_at = None
                self._set_button_active()
                self._tick()

    def _on_top_field_change(self, *_):
        if self._running_id is None:
            return
        desc    = self._desc_var.get().strip()
        project = self._proj_var.get().strip() or None
        db.update_log(self._running_id, self._running_start, None, desc, project)

    # ── Window management ──────────────────────────────────────────────────────

    def _open_history(self):
        if self._history_win and self._history_win.winfo_exists():
            self._history_win.lift()
            self._history_win.focus_force()
            return
        self._history_win = HistoryWindow(self)
        self._history_win._filter_callback = self._refresh_log_list
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

    def _open_add_entry(self):
        AddEntryModal(self, on_save_callback=self._refresh_log_list)

    # ── Log list ───────────────────────────────────────────────────────────────

    def _refresh_log_list(self):
        projects = db.get_distinct_projects()
        self._proj_combo.configure(values=projects)

        if not (self._history_win and self._history_win.winfo_exists()):
            return

        hw = self._history_win

        # Update project list in the filter combo
        hw._filter_proj_combo.configure(values=[""] + projects)

        # Read active filter values
        proj_filter = hw._filter_proj_var.get().strip() or None
        from_filter = hw._filter_from_var.get().strip() or None
        to_filter   = hw._filter_to_var.get().strip() or None
        kw_filter   = hw._filter_kw_var.get().strip() or None

        # Silently ignore malformed date values in the filter bar
        for val in (from_filter, to_filter):
            if val:
                try:
                    datetime.strptime(val, DATE_FMT)
                except ValueError:
                    # Replace with None so it's not passed to the query
                    if val == from_filter:
                        from_filter = None
                    else:
                        to_filter = None

        rows = db.get_filtered_logs(proj_filter, from_filter, to_filter, kw_filter)

        for widget in hw.scroll_frame.winfo_children():
            widget.destroy()

        total_seconds = 0
        for row in rows:
            if row["end_time"]:
                delta = (datetime.strptime(row["end_time"], DT_FMT) -
                         datetime.strptime(row["start_time"], DT_FMT))
                paused = int(row["paused_duration"] or 0)
                total_seconds += max(0, int(delta.total_seconds()) - paused)

        th, tm = divmod(total_seconds // 60, 60)
        hw.total_label.configure(text=f"Total: {th}h {tm:02d}m")

        for r_idx, row in enumerate(rows):
            bg = ("#e8e8e8", "#2b2b2b") if r_idx % 2 == 0 else ("#f5f5f5", "#333333")
            self._add_log_row(hw.scroll_frame, r_idx, dict(row), bg)

    def _add_log_row(self, scroll_frame, r_idx: int, row: dict, bg):
        start_dt = datetime.strptime(row["start_time"], DT_FMT)
        date_str  = start_dt.strftime(DATE_FMT)
        start_str = start_dt.strftime(DISPLAY_TIME_FMT)
        paused_secs = int(row.get("paused_duration") or 0)

        if row["end_time"]:
            end_dt  = datetime.strptime(row["end_time"], DT_FMT)
            end_str = end_dt.strftime(DISPLAY_TIME_FMT)
            dur_str = _duration_label(row["start_time"], row["end_time"], paused_secs)
        else:
            end_str = "──"
            dur_str = "⏸ paused" if row.get("paused_at") else "(running)"

        values  = [date_str, start_str, end_str, dur_str,
                   row["description"] or "", row["project"] or ""]
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
            lbl.bind("<Enter>",          _on_enter)
            lbl.bind("<Leave>",          _on_leave)
            lbl.bind("<Double-Button-1>", lambda e, r=row: self._open_edit(r))

        ctk.CTkButton(
            scroll_frame, text="Edit", width=50, height=24,
            command=lambda r=row: self._open_edit(r),
        ).grid(row=r_idx, column=6, padx=2, pady=0)

        ctk.CTkButton(
            scroll_frame, text="Del", width=50, height=24,
            fg_color="#c62828", hover_color="#b71c1c",
            command=lambda r=row: self._delete_entry(r),
        ).grid(row=r_idx, column=7, padx=2, pady=0)

    def _open_edit(self, row: dict):
        EditModal(self, row, on_save_callback=self._refresh_log_list)

    def _delete_entry(self, row: dict):
        confirmed = messagebox.askyesno(
            "Delete Entry", "Delete this entry? This cannot be undone.", parent=self,
        )
        if not confirmed:
            return
        if row["id"] == self._running_id:
            self._running_id     = None
            self._running_start  = None
            self._paused_at      = None
            self._paused_seconds = 0
            if self._tick_job:
                self.after_cancel(self._tick_job)
                self._tick_job = None
            self._set_button_idle()
        db.delete_log(row["id"])
        self._refresh_log_list()

    # ── System tray (U1) ──────────────────────────────────────────────────────

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show LedgerTimer", self._show_window, default=True),
            pystray.MenuItem(
                "Stop Timer", self._tray_stop_timer,
                enabled=lambda item: self._running_id is not None,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_from_tray),
        )
        self._tray_icon = pystray.Icon(
            "LedgerTimer",
            _make_tray_image(running=False),
            "LedgerTimer",
            menu,
        )

    def _on_close(self):
        """Hide to tray instead of destroying the window."""
        if _TRAY_AVAILABLE and self._tray_icon:
            self.withdraw()
            if not self._tray_icon.visible:
                threading.Thread(target=self._tray_icon.run, daemon=True).start()
        else:
            self.destroy()

    def _show_window(self, icon=None, item=None):
        self.after(0, lambda: (
            self.deiconify(),
            self.lift(),
            self.focus_force(),
        ))

    def _tray_stop_timer(self, icon=None, item=None):
        if self._running_id is not None:
            self.after(0, self._stop_timer)

    def _quit_from_tray(self, icon=None, item=None):
        if self._tray_icon:
            self._tray_icon.stop()
        self.after(0, self.destroy)

    def _update_tray(self, running: bool):
        if self._tray_icon and _TRAY_AVAILABLE:
            try:
                self._tray_icon.icon = _make_tray_image(running=running)
            except Exception:
                pass

    def _update_tray_tooltip(self, elapsed: str):
        if self._tray_icon and _TRAY_AVAILABLE:
            try:
                self._tray_icon.title = f"LedgerTimer — {elapsed}"
            except Exception:
                pass
