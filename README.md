# ⏱️ LedgerTimer

A lightweight, open-source, privacy-first desktop time tracker built with **Python** and **CustomTkinter**. 

`LedgerTimer` is designed specifically for freelancers, contractors, and professionals who need to log billable hours for clients. It features a simple punch-in/punch-out interface, flexible retroactive editing, and clean end-of-month CSV/Excel exports for seamless invoicing.

---

## ✨ Features (Target MVP)

* **Manual Punch In/Out:** A prominent, simple button interface to record work sessions in real-time.
* **Retroactive Time Editing:** Complete freedom to modify the Start Time, End Time, or overall duration of any log after an activity is completed (to correct mistakes).
* **Detailed Task Descriptions:** An input field for every session to note down exactly what work was done, ensuring complete transparency for your clients.
* **Client/Project Tagging:** Easily categorize each logged session under specific clients or projects.
* **End-of-Month Export:** One-click data export to standard `.csv` (Excel-compatible) formats, filtered by date range or client for quick billing.
* **Local & Secure Storage:** Uses a lightweight, local SQLite database to store all historical logs safely on your machine.

---

## 🏗️ Architecture & Technology Stack

* **Language:** Python 3.10+
* **GUI Framework:** `customtkinter` (Modern, sleek, dark/light mode responsive widgets)
* **Data Storage:** `sqlite3` (Built into Python, zero setup required)
* **Data Export:** Python's native `csv` module
* **Packaging Tool:** `PyInstaller` for single-file executable distribution (`.exe`, `.app`, or Linux binary)

---

## 🤖 AI Assistant Instructions (System Prompt for Coding)

> **Hey AI!** Please strictly follow these engineering guidelines when helping me write, debug, or refactor code for LedgerTimer:

1.  **Keep it Simple & Modular:** Keep the UI layer (`gui.py`), database layer (`database.py`), and export logic (`export.py`) cleanly separated.
2.  **CustomTkinter Elements Only:** Always use `customtkinter` elements (e.g., `CTkButton`, `CTkEntry`, `CTkTextbox`, `CTkFrame`) instead of raw `tkinter` widgets to keep the dark-mode aesthetic consistent.
3.  **UI Layout Blueprint:** * **Top Section:** Client/Project selector, Task Description input box, and a prominent Start/Stop Timer button with a live running clock.
    * **Middle Section:** A scrollable table or list showing today's logged activities. Double-clicking a log should open a clean modal/popup to let the user manually edit the start/end times and descriptions.
    * **Bottom Section:** Date-range filters and a prominent "Export to CSV" button.
4.  **Database Resiliency:** Ensure the SQLite database automatically initializes its tables (`logs`, `projects`) on the very first boot if they don't already exist.

---

## 🚀 Getting Started (Development Setup)

### Prerequisites
* Python 3.10 or higher
* `pip` (Python package manager)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/vincent7q/LedgerTimer.git
   cd LedgerTimer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the program:
   ```bash
   python -m ledgertimer
   ```

---

## 📦 Building a Windows Executable

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. (Optional) Regenerate the app icon if needed:
   ```bash
   python ledgertimer/ico_generator.py
   ```
   This creates `ledgertimer/app_icon.ico`. The file is already committed, so skip this step unless you want to update the icon.

3. Build using the spec file (recommended):
   ```bash
   python -m PyInstaller LedgerTimer.spec --noconfirm
   ```

   The spec file handles everything automatically:

   | Setting | Value |
   |---|---|
   | Single-file output | `--onefile` |
   | No console window | `--windowed` |
   | CustomTkinter assets | bundled via `collect_data_files` |
   | App icon (window + taskbar) | `ledgertimer/app_icon.ico` |
   | Exe icon (file explorer) | `ledgertimer/app_icon.ico` |

   > **Do not** use a raw `pyinstaller --onefile ...` command — it will regenerate the spec and lose the icon settings.

4. The finished executable is at:
   ```
   dist/LedgerTimer.exe
   ```
   `ledger.db` will be created automatically in the same folder as the `.exe` on first run.

---

## 🐧 Building a Linux Executable

PyInstaller cannot cross-compile — the Linux binary must be built **on Linux**. The easiest way on Windows is via **WSL2**.

### Using WSL2

1. Install WSL2 and a distro (e.g. Ubuntu) if not already set up:
   ```powershell
   wsl --install
   ```

2. Open a WSL terminal, navigate to the project, and install dependencies:
   ```bash
   cd /mnt/c/Users/<you>/source/LedgerTimer
   sudo apt update && sudo apt install python3 python3-pip python3-tk -y
   pip3 install -r requirements.txt
   pip3 install pyinstaller
   ```

3. Build using the same spec file:
   ```bash
   python3 -m PyInstaller LedgerTimer.spec --noconfirm
   ```

   > The `icon=` setting in the spec is silently ignored on Linux — this is expected.

4. The finished binary is at:
   ```
   dist/LedgerTimer
   ```
   Make it executable if needed:
   ```bash
   chmod +x dist/LedgerTimer
   ./dist/LedgerTimer
   ```

### Using a Linux VM or CI
If you prefer a VM or CI pipeline (e.g. GitHub Actions), the same steps apply — install Python + tkinter, install dependencies, then run `pyinstaller LedgerTimer.spec --noconfirm`.

---

## 🍎 Building a macOS App

Like Linux, macOS builds must be run **on a Mac** (no cross-compilation).

### Steps

1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/) (recommended over Homebrew — it includes Tkinter).

2. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   pip3 install pyinstaller
   ```

3. (Optional) Generate a macOS `.icns` icon. The `.ico` file used for Windows is not supported on macOS:
   ```bash
   # Convert app_icon.ico to app_icon.icns using sips + iconutil (macOS built-in tools)
   mkdir app_icon.iconset
   sips -z 16 16   ledgertimer/app_icon.png --out app_icon.iconset/icon_16x16.png
   sips -z 32 32   ledgertimer/app_icon.png --out app_icon.iconset/icon_16x16@2x.png
   sips -z 32 32   ledgertimer/app_icon.png --out app_icon.iconset/icon_32x32.png
   sips -z 64 64   ledgertimer/app_icon.png --out app_icon.iconset/icon_32x32@2x.png
   sips -z 128 128 ledgertimer/app_icon.png --out app_icon.iconset/icon_128x128.png
   sips -z 256 256 ledgertimer/app_icon.png --out app_icon.iconset/icon_128x128@2x.png
   sips -z 256 256 ledgertimer/app_icon.png --out app_icon.iconset/icon_256x256.png
   sips -z 512 512 ledgertimer/app_icon.png --out app_icon.iconset/icon_256x256@2x.png
   iconutil -c icns app_icon.iconset -o ledgertimer/app_icon.icns
   rm -rf app_icon.iconset
   ```
   Then update the `icon=` line in `LedgerTimer.spec` to `'ledgertimer/app_icon.icns'` before building.

4. Build using the spec file:
   ```bash
   python3 -m PyInstaller LedgerTimer.spec --noconfirm
   ```

5. The finished app bundle is at:
   ```
   dist/LedgerTimer.app
   ```
   To run it:
   ```bash
   open dist/LedgerTimer.app
   ```

> **Gatekeeper warning**: Unsigned apps downloaded from the internet will be blocked by macOS. To bypass for local use, right-click → Open, or run:
> ```bash
> xattr -d com.apple.quarantine dist/LedgerTimer.app
> ```