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
   git clone [https://github.com/YOUR_USERNAME/LedgerTimer.git](https://github.com/YOUR_USERNAME/LedgerTimer.git)
   cd LedgerTimer
