# Go LedgerTimer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform desktop time tracker in Go (Fyne GUI) outputting a single binary for Windows, macOS, and Linux, placed in the `go/` subfolder.

**Architecture:** Flat `package main` in `go/` — `db.go` owns the SQLite data layer, `export.go` owns CSV writing, `ui.go` owns all Fyne widget construction and view-switching, `main.go` is the entry point. The Fyne window swaps its entire content (`window.SetContent`) when navigating between Timer, History, and Export views.

**Tech Stack:** Go 1.22+, `fyne.io/fyne/v2` (GUI, OpenGL-based), `modernc.org/sqlite` (pure-Go SQLite — no CGO required for DB layer)

---

### Task 1: Module scaffold

**Files:**
- Create: `go/go.mod`

- [ ] **Step 1: Create the `go/` directory and initialize the module**

Run from the repo root:
```powershell
mkdir go
cd go
go mod init ledgertimer
```

- [ ] **Step 2: Add dependencies**

```powershell
go get fyne.io/fyne/v2
go get modernc.org/sqlite
go mod tidy
```

- [ ] **Step 3: Verify `go.mod` has both dependencies** (exact versions will differ — that's fine)

```
module ledgertimer

go 1.22

require (
    fyne.io/fyne/v2 v2.5.1
    modernc.org/sqlite v1.33.1
)
```

- [ ] **Step 4: Commit**

```bash
git add go/go.mod go/go.sum
git commit -m "feat(go): add Go module scaffold with Fyne and SQLite"
```

---

### Task 2: DB layer (`go/db.go` + `go/db_test.go`)

**Files:**
- Create: `go/db.go`
- Create: `go/db_test.go`

- [ ] **Step 1: Create `go/db.go`**

```go
package main

import (
	"database/sql"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

const dtFmt = "2006-01-02T15:04:05"

// LogEntry mirrors one row in the logs table.
type LogEntry struct {
	ID          int64
	StartTime   string // "2006-01-02T15:04:05"
	EndTime     string // empty string when still running
	Description string
	Project     string
}

var _db *sql.DB

func dbFilePath() string {
	exe, err := os.Executable()
	if err != nil {
		return "ledger.db"
	}
	return filepath.Join(filepath.Dir(exe), "ledger.db")
}

// InitDB opens (or creates) ledger.db next to the executable.
func InitDB() error {
	return initDBWithPath(dbFilePath())
}

func initDBWithPath(path string) error {
	var err error
	_db, err = sql.Open("sqlite", path)
	if err != nil {
		return err
	}
	_, err = _db.Exec(`CREATE TABLE IF NOT EXISTS logs (
		id          INTEGER PRIMARY KEY AUTOINCREMENT,
		start_time  TEXT NOT NULL,
		end_time    TEXT,
		description TEXT NOT NULL DEFAULT '',
		project     TEXT
	)`)
	return err
}

// StartTimer inserts a running entry and returns its row ID.
func StartTimer(start, desc, project string) (int64, error) {
	var proj interface{}
	if project != "" {
		proj = project
	}
	res, err := _db.Exec(
		"INSERT INTO logs (start_time, description, project) VALUES (?, ?, ?)",
		start, desc, proj,
	)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

// StopTimer sets end_time on the given log entry.
func StopTimer(id int64, end string) error {
	_, err := _db.Exec("UPDATE logs SET end_time = ? WHERE id = ?", end, id)
	return err
}

// GetRunningEntry returns the single entry with no end_time, or nil.
func GetRunningEntry() (*LogEntry, error) {
	row := _db.QueryRow(
		"SELECT id, start_time, COALESCE(description,''), COALESCE(project,'') FROM logs WHERE end_time IS NULL LIMIT 1",
	)
	var e LogEntry
	if err := row.Scan(&e.ID, &e.StartTime, &e.Description, &e.Project); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	return &e, nil
}

// GetAllLogs returns all log entries, most recent first.
func GetAllLogs() ([]LogEntry, error) {
	rows, err := _db.Query(
		"SELECT id, start_time, COALESCE(end_time,''), COALESCE(description,''), COALESCE(project,'') FROM logs ORDER BY start_time DESC",
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var entries []LogEntry
	for rows.Next() {
		var e LogEntry
		if err := rows.Scan(&e.ID, &e.StartTime, &e.EndTime, &e.Description, &e.Project); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}
	return entries, nil
}

// GetLogsForExport returns completed entries whose start date falls within [from, to].
func GetLogsForExport(from, to string) ([]LogEntry, error) {
	rows, err := _db.Query(`
		SELECT id, start_time, end_time, COALESCE(description,''), COALESCE(project,'')
		FROM logs
		WHERE end_time IS NOT NULL
		  AND DATE(start_time) >= ?
		  AND DATE(start_time) <= ?
		ORDER BY start_time ASC`, from, to)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var entries []LogEntry
	for rows.Next() {
		var e LogEntry
		if err := rows.Scan(&e.ID, &e.StartTime, &e.EndTime, &e.Description, &e.Project); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}
	return entries, nil
}

// UpdateLog performs a full update on a log entry.
// Pass end as "" to leave end_time NULL (still running).
func UpdateLog(id int64, start, end, desc, project string) error {
	var endVal, projVal interface{}
	if end != "" {
		endVal = end
	}
	if project != "" {
		projVal = project
	}
	_, err := _db.Exec(
		"UPDATE logs SET start_time=?, end_time=?, description=?, project=? WHERE id=?",
		start, endVal, desc, projVal, id,
	)
	return err
}

// DeleteLog removes a log entry by ID.
func DeleteLog(id int64) error {
	_, err := _db.Exec("DELETE FROM logs WHERE id = ?", id)
	return err
}

// GetDistinctProjects returns sorted distinct non-null project names.
func GetDistinctProjects() ([]string, error) {
	rows, err := _db.Query(
		"SELECT DISTINCT project FROM logs WHERE project IS NOT NULL ORDER BY project",
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var projects []string
	for rows.Next() {
		var p string
		if err := rows.Scan(&p); err != nil {
			return nil, err
		}
		projects = append(projects, p)
	}
	return projects, nil
}
```

- [ ] **Step 2: Create `go/db_test.go`**

```go
package main

import (
	"testing"
)

func setupTestDB(t *testing.T) {
	t.Helper()
	path := t.TempDir() + "/test.db"
	if err := initDBWithPath(path); err != nil {
		t.Fatal("initDBWithPath:", err)
	}
	t.Cleanup(func() {
		if _db != nil {
			_db.Close()
			_db = nil
		}
	})
}

func TestStartTimerReturnsPositiveID(t *testing.T) {
	setupTestDB(t)
	id, err := StartTimer("2026-05-26T09:00:00", "Task", "ProjectA")
	if err != nil {
		t.Fatal(err)
	}
	if id <= 0 {
		t.Errorf("want id > 0, got %d", id)
	}
}

func TestGetRunningEntryAfterStart(t *testing.T) {
	setupTestDB(t)
	StartTimer("2026-05-26T09:00:00", "Task", "")
	entry, err := GetRunningEntry()
	if err != nil {
		t.Fatal(err)
	}
	if entry == nil {
		t.Fatal("want running entry, got nil")
	}
	if entry.EndTime != "" {
		t.Errorf("want empty EndTime, got %q", entry.EndTime)
	}
}

func TestStopTimerClearsRunning(t *testing.T) {
	setupTestDB(t)
	id, _ := StartTimer("2026-05-26T09:00:00", "Task", "")
	StopTimer(id, "2026-05-26T10:30:00")
	entry, err := GetRunningEntry()
	if err != nil {
		t.Fatal(err)
	}
	if entry != nil {
		t.Error("want nil running entry after stop, got one")
	}
}

func TestDeleteLogRemovesEntry(t *testing.T) {
	setupTestDB(t)
	id, _ := StartTimer("2026-05-26T09:00:00", "To delete", "")
	StopTimer(id, "2026-05-26T10:00:00")
	DeleteLog(id)
	logs, _ := GetAllLogs()
	for _, e := range logs {
		if e.ID == id {
			t.Error("deleted entry still present in GetAllLogs")
		}
	}
}

func TestGetLogsForExportExcludesRunning(t *testing.T) {
	setupTestDB(t)
	id1, _ := StartTimer("2026-05-26T09:00:00", "Done", "")
	StopTimer(id1, "2026-05-26T10:00:00")
	StartTimer("2026-05-26T11:00:00", "Still running", "")
	rows, err := GetLogsForExport("2026-05-26", "2026-05-26")
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 {
		t.Fatalf("want 1 exported row, got %d", len(rows))
	}
	if rows[0].ID != id1 {
		t.Errorf("want id %d, got %d", id1, rows[0].ID)
	}
}

func TestGetLogsForExportDateFilter(t *testing.T) {
	setupTestDB(t)
	id1, _ := StartTimer("2026-05-10T09:00:00", "May 10", "")
	StopTimer(id1, "2026-05-10T10:00:00")
	id2, _ := StartTimer("2026-06-01T09:00:00", "June 1", "")
	StopTimer(id2, "2026-06-01T10:00:00")
	rows, _ := GetLogsForExport("2026-05-01", "2026-05-31")
	if len(rows) != 1 || rows[0].ID != id1 {
		t.Errorf("date filter: got %d rows (want 1 with id %d)", len(rows), id1)
	}
}

func TestUpdateLog(t *testing.T) {
	setupTestDB(t)
	id, _ := StartTimer("2026-05-26T09:00:00", "Original", "Old")
	StopTimer(id, "2026-05-26T10:00:00")
	UpdateLog(id, "2026-05-26T08:00:00", "2026-05-26T09:30:00", "Updated", "New")
	logs, _ := GetAllLogs()
	var updated *LogEntry
	for i := range logs {
		if logs[i].ID == id {
			updated = &logs[i]
		}
	}
	if updated == nil {
		t.Fatal("updated entry not found")
	}
	if updated.Description != "Updated" {
		t.Errorf("description: want 'Updated', got %q", updated.Description)
	}
	if updated.Project != "New" {
		t.Errorf("project: want 'New', got %q", updated.Project)
	}
}

func TestGetDistinctProjects(t *testing.T) {
	setupTestDB(t)
	id1, _ := StartTimer("2026-05-26T09:00:00", "", "Alpha")
	StopTimer(id1, "2026-05-26T10:00:00")
	id2, _ := StartTimer("2026-05-26T11:00:00", "", "Beta")
	StopTimer(id2, "2026-05-26T12:00:00")
	StartTimer("2026-05-26T13:00:00", "", "Alpha") // duplicate, still running
	projects, err := GetDistinctProjects()
	if err != nil {
		t.Fatal(err)
	}
	if len(projects) != 2 {
		t.Fatalf("want 2 distinct projects, got %d: %v", len(projects), projects)
	}
	if projects[0] != "Alpha" || projects[1] != "Beta" {
		t.Errorf("want [Alpha Beta], got %v", projects)
	}
}
```

- [ ] **Step 3: Run the tests**

```powershell
cd go
go test -v ./...
```

Expected: 8 tests, all PASS.

- [ ] **Step 4: Commit**

```bash
git add go/db.go go/db_test.go
git commit -m "feat(go): add SQLite data layer with tests"
```

---

### Task 3: Export layer (`go/export.go` + `go/export_test.go`)

**Files:**
- Create: `go/export.go`
- Create: `go/export_test.go`

- [ ] **Step 1: Create `go/export.go`**

```go
package main

import (
	"encoding/csv"
	"fmt"
	"io"
	"time"
)

// ExportToCSV writes log entries to w in CSV format.
// Returns the number of rows written.
func ExportToCSV(rows []LogEntry, w io.Writer) (int, error) {
	cw := csv.NewWriter(w)
	if err := cw.Write([]string{"Date", "Start Time", "End Time", "Duration", "Description", "Project"}); err != nil {
		return 0, err
	}
	count := 0
	for _, row := range rows {
		start, err := time.Parse(dtFmt, row.StartTime)
		if err != nil {
			continue
		}
		end, err := time.Parse(dtFmt, row.EndTime)
		if err != nil {
			continue
		}
		hours := end.Sub(start).Hours()
		if err := cw.Write([]string{
			start.Format("2006-01-02"),
			start.Format("15:04"),
			end.Format("15:04"),
			fmt.Sprintf("%.2f", hours),
			row.Description,
			row.Project,
		}); err != nil {
			return count, err
		}
		count++
	}
	cw.Flush()
	return count, cw.Error()
}
```

- [ ] **Step 2: Create `go/export_test.go`**

```go
package main

import (
	"bytes"
	"encoding/csv"
	"strings"
	"testing"
)

func TestExportReturnsRowCount(t *testing.T) {
	rows := []LogEntry{
		{StartTime: "2026-05-26T09:00:00", EndTime: "2026-05-26T10:30:00"},
	}
	var buf bytes.Buffer
	count, err := ExportToCSV(rows, &buf)
	if err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Errorf("want 1, got %d", count)
	}
}

func TestExportCSVHeaders(t *testing.T) {
	var buf bytes.Buffer
	ExportToCSV(nil, &buf)
	r := csv.NewReader(strings.NewReader(buf.String()))
	headers, err := r.Read()
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"Date", "Start Time", "End Time", "Duration", "Description", "Project"}
	for i, h := range want {
		if i >= len(headers) || headers[i] != h {
			t.Errorf("header[%d]: want %q, got %q", i, h, headers[i])
		}
	}
}

func TestExportCSVValues(t *testing.T) {
	rows := []LogEntry{
		{
			StartTime:   "2026-05-26T09:00:00",
			EndTime:     "2026-05-26T10:45:00",
			Description: "Code review",
			Project:     "ClientB",
		},
	}
	var buf bytes.Buffer
	ExportToCSV(rows, &buf)
	r := csv.NewReader(strings.NewReader(buf.String()))
	r.Read() // skip header
	record, err := r.Read()
	if err != nil {
		t.Fatal(err)
	}
	checks := map[int]string{0: "2026-05-26", 1: "09:00", 2: "10:45", 3: "1.75", 4: "Code review", 5: "ClientB"}
	for col, want := range checks {
		if record[col] != want {
			t.Errorf("col %d: want %q, got %q", col, want, record[col])
		}
	}
}

func TestExportDurationDecimal(t *testing.T) {
	// 90 minutes = 1.50 decimal hours
	rows := []LogEntry{
		{StartTime: "2026-05-26T08:00:00", EndTime: "2026-05-26T09:30:00"},
	}
	var buf bytes.Buffer
	ExportToCSV(rows, &buf)
	r := csv.NewReader(strings.NewReader(buf.String()))
	r.Read() // skip header
	record, _ := r.Read()
	if record[3] != "1.50" {
		t.Errorf("duration: want 1.50, got %s", record[3])
	}
}

func TestExportEmptyDescriptionAndProject(t *testing.T) {
	rows := []LogEntry{
		{StartTime: "2026-05-26T09:00:00", EndTime: "2026-05-26T09:30:00"},
	}
	var buf bytes.Buffer
	ExportToCSV(rows, &buf)
	r := csv.NewReader(strings.NewReader(buf.String()))
	r.Read() // skip header
	record, _ := r.Read()
	if record[4] != "" || record[5] != "" {
		t.Errorf("want empty description and project, got %q %q", record[4], record[5])
	}
}
```

- [ ] **Step 3: Run the tests**

```powershell
go test -run TestExport -v
```

Expected: 5 tests, all PASS.

- [ ] **Step 4: Commit**

```bash
git add go/export.go go/export_test.go
git commit -m "feat(go): add CSV export with tests"
```

---

### Task 4: App skeleton (`go/main.go` + `go/ui.go`)

**Files:**
- Create: `go/main.go`
- Create: `go/ui.go`

- [ ] **Step 1: Create `go/main.go`**

```go
package main

import (
	"log"

	"fyne.io/fyne/v2/app"
)

func main() {
	if err := InitDB(); err != nil {
		log.Fatal("DB init failed:", err)
	}
	fyneApp := app.New()
	a := newApp(fyneApp)
	a.run()
}
```

- [ ] **Step 2: Create `go/ui.go` with the App struct, constructor, menu, date helpers, and stubs for all view functions**

```go
package main

import (
	"fmt"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"
)

// Suppress unused-import errors until view functions are implemented in later tasks.
var (
	_ = fmt.Sprintf
	_ = container.NewVBox
	_ = dialog.ShowError
)

// App holds all UI state and widget references.
type App struct {
	fyneApp fyne.App
	window  fyne.Window

	// timer view — built once at startup, reused when navigating back
	timerContent fyne.CanvasObject

	// timer view widget refs (needed for updates after state changes)
	projectEntry *widget.SelectEntry
	descEntry    *widget.Entry
	startStopBtn *widget.Button
	clockLabel   *widget.Label
	discardBtn   *widget.Button

	// timer state
	runningID    int64
	runningStart time.Time
	tickerDone   chan struct{}
}

func newApp(fyneApp fyne.App) *App {
	a := &App{fyneApp: fyneApp}
	a.window = fyneApp.NewWindow("LedgerTimer")
	a.window.Resize(fyne.NewSize(720, 380))
	return a
}

func (a *App) run() {
	a.buildTimerView()
	a.buildMenu()
	a.window.SetContent(a.timerContent)
	a.restoreRunningState()
	a.window.ShowAndRun()
}

func (a *App) buildMenu() {
	fileMenu := fyne.NewMenu("File",
		fyne.NewMenuItem("Quit", a.fyneApp.Quit),
	)
	historyMenu := fyne.NewMenu("History",
		fyne.NewMenuItem("Show History", func() {
			a.window.SetContent(a.buildHistoryView())
		}),
	)
	exportMenu := fyne.NewMenu("Export",
		fyne.NewMenuItem("Export to CSV", func() {
			a.window.SetContent(a.buildExportView())
		}),
	)
	a.window.SetMainMenu(fyne.NewMainMenu(fileMenu, historyMenu, exportMenu))
}

func firstOfMonth() string {
	now := time.Now()
	return time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.Local).Format("2006-01-02")
}

func lastOfMonth() string {
	now := time.Now()
	first := time.Date(now.Year(), now.Month()+1, 1, 0, 0, 0, 0, time.Local)
	return first.AddDate(0, 0, -1).Format("2006-01-02")
}

// --- stubs replaced in Tasks 5–8 ---

func (a *App) buildTimerView() {
	a.timerContent = widget.NewLabel("Timer coming soon")
}
func (a *App) refreshProjects() {}
func (a *App) toggleTimer()                                 {}
func (a *App) startTimer()                                  {}
func (a *App) stopTimer()                                   {}
func (a *App) discardTimer()                                {}
func (a *App) startTicker()                                 {}
func (a *App) stopTicker()                                  {}
func (a *App) restoreRunningState()                         {}
func (a *App) buildHistoryView() fyne.CanvasObject          { return widget.NewLabel("History coming soon") }
func (a *App) showEditDialog(_ LogEntry, _ func())          {}
func (a *App) buildExportView() fyne.CanvasObject           { return widget.NewLabel("Export coming soon") }
```

- [ ] **Step 3: Verify the app compiles**

```powershell
go build .
```

Expected: compiles with no errors. (Window would be blank — `buildTimerView` is a stub.)

- [ ] **Step 4: Commit**

```bash
git add go/main.go go/ui.go
git commit -m "feat(go): add app skeleton with menu bar and view stubs"
```

---

### Task 5: Timer view UI (`buildTimerView` + `refreshProjects`)

**Files:**
- Modify: `go/ui.go`

- [ ] **Step 1: Replace the `buildTimerView` and `refreshProjects` stubs**

Remove:
```go
func (a *App) buildTimerView()  {}
func (a *App) refreshProjects() {}
```

Add:
```go
func (a *App) buildTimerView() {
	projects, _ := GetDistinctProjects()

	a.projectEntry = widget.NewSelectEntry(projects)
	a.projectEntry.SetPlaceHolder("Project (optional)")

	a.descEntry = widget.NewEntry()
	a.descEntry.SetPlaceHolder("Description (optional)")

	a.clockLabel = widget.NewLabel("")
	a.clockLabel.Alignment = fyne.TextAlignCenter
	a.clockLabel.TextStyle = fyne.TextStyle{Bold: true}
	a.clockLabel.Hide()

	a.discardBtn = widget.NewButton("✕  Discard", a.discardTimer)
	a.discardBtn.Hide()

	a.startStopBtn = widget.NewButton("▶  Start", a.toggleTimer)

	// Live-sync description/project to the running DB row on every keystroke.
	a.descEntry.OnChanged = func(s string) {
		if a.runningID != 0 {
			UpdateLog(a.runningID, a.runningStart.Format(dtFmt), "", s, a.projectEntry.Text)
		}
	}
	a.projectEntry.OnChanged = func(s string) {
		if a.runningID != 0 {
			UpdateLog(a.runningID, a.runningStart.Format(dtFmt), "", a.descEntry.Text, s)
		}
	}

	form := widget.NewForm(
		widget.NewFormItem("Project", a.projectEntry),
		widget.NewFormItem("Description", a.descEntry),
	)

	a.timerContent = container.NewVBox(
		form,
		a.startStopBtn,
		a.clockLabel,
		a.discardBtn,
	)
}

func (a *App) refreshProjects() {
	projects, _ := GetDistinctProjects()
	a.projectEntry.SetOptions(projects)
}
```

- [ ] **Step 2: Remove the `container` suppression line** (it's now used by `buildTimerView`)

Remove:
```go
_ = container.NewVBox
```

- [ ] **Step 3: Verify it compiles**

```powershell
go build .
```

- [ ] **Step 4: Commit**

```bash
git add go/ui.go
git commit -m "feat(go): build timer view UI widgets"
```

---

### Task 6: Timer logic (start, stop, discard, ticker, restore)

**Files:**
- Modify: `go/ui.go`

- [ ] **Step 1: Remove the timer-logic stubs**

Remove these lines:
```go
func (a *App) toggleTimer()         {}
func (a *App) startTimer()          {}
func (a *App) stopTimer()           {}
func (a *App) discardTimer()        {}
func (a *App) startTicker()         {}
func (a *App) stopTicker()          {}
func (a *App) restoreRunningState() {}
```

- [ ] **Step 2: Add the real timer logic**

```go
func (a *App) toggleTimer() {
	if a.runningID == 0 {
		a.startTimer()
	} else {
		a.stopTimer()
	}
}

func (a *App) startTimer() {
	start := time.Now().Format(dtFmt)
	id, err := StartTimer(start, a.descEntry.Text, a.projectEntry.Text)
	if err != nil {
		dialog.ShowError(err, a.window)
		return
	}
	a.runningID = id
	a.runningStart, _ = time.Parse(dtFmt, start)
	a.startStopBtn.SetText("■  Stop")
	a.clockLabel.Show()
	a.discardBtn.Show()
	a.startTicker()
	a.refreshProjects()
}

func (a *App) stopTimer() {
	end := time.Now().Format(dtFmt)
	if err := StopTimer(a.runningID, end); err != nil {
		dialog.ShowError(err, a.window)
		return
	}
	a.stopTicker()
	a.runningID = 0
	a.descEntry.SetText("")
	a.projectEntry.SetText("")
	a.startStopBtn.SetText("▶  Start")
	a.clockLabel.Hide()
	a.discardBtn.Hide()
	a.refreshProjects()
}

func (a *App) discardTimer() {
	dialog.ShowConfirm(
		"Discard Timer",
		"Delete this timer entry? The time will not be saved.",
		func(ok bool) {
			if !ok {
				return
			}
			DeleteLog(a.runningID)
			a.stopTicker()
			a.runningID = 0
			a.descEntry.SetText("")
			a.projectEntry.SetText("")
			a.startStopBtn.SetText("▶  Start")
			a.clockLabel.Hide()
			a.discardBtn.Hide()
		},
		a.window,
	)
}

func (a *App) startTicker() {
	a.tickerDone = make(chan struct{})
	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				elapsed := time.Since(a.runningStart)
				h := int(elapsed.Hours())
				m := int(elapsed.Minutes()) % 60
				s := int(elapsed.Seconds()) % 60
				a.clockLabel.SetText(fmt.Sprintf("%02d:%02d:%02d", h, m, s))
			case <-a.tickerDone:
				return
			}
		}
	}()
}

func (a *App) stopTicker() {
	if a.tickerDone != nil {
		close(a.tickerDone)
		a.tickerDone = nil
	}
}

func (a *App) restoreRunningState() {
	entry, err := GetRunningEntry()
	if err != nil || entry == nil {
		return
	}
	a.runningID = entry.ID
	a.runningStart, _ = time.Parse(dtFmt, entry.StartTime)
	a.descEntry.SetText(entry.Description)
	a.projectEntry.SetText(entry.Project)
	a.startStopBtn.SetText("■  Stop")
	a.clockLabel.Show()
	a.discardBtn.Show()
	a.startTicker()
}
```

- [ ] **Step 3: Remove the remaining suppression lines** (`fmt` and `dialog` are now used)

At this point the var block still contains two lines (the `container` line was removed in Task 5). Remove it entirely:

```go
var (
	_ = fmt.Sprintf
	_ = dialog.ShowError
)
```

- [ ] **Step 4: Build and smoke-test the timer**

```powershell
go build -o LedgerTimer.exe .
./LedgerTimer.exe
```

Expected: Window opens. Click Start — clock ticks. Click Stop — resets. Click Discard (while running) — confirm dialog appears, entry is removed.

- [ ] **Step 5: Commit**

```bash
git add go/ui.go
git commit -m "feat(go): implement timer start/stop/discard/tick/restore"
```

---

### Task 7: History view + edit dialog

**Files:**
- Modify: `go/ui.go`

- [ ] **Step 1: Remove the history stubs**

Remove:
```go
func (a *App) buildHistoryView() fyne.CanvasObject { return widget.NewLabel("History coming soon") }
func (a *App) showEditDialog(_ LogEntry, _ func())  {}
```

- [ ] **Step 2: Add `buildHistoryView` and `showEditDialog`**

```go
func (a *App) buildHistoryView() fyne.CanvasObject {
	logs, _ := GetAllLogs()

	backBtn := widget.NewButton("← Back", func() {
		a.window.SetContent(a.timerContent)
	})

	vbox := container.NewVBox()
	for _, entry := range logs {
		entry := entry // capture loop variable

		startT, _ := time.Parse(dtFmt, entry.StartTime)
		dateStr := startT.Format("2006-01-02")
		startStr := startT.Format("15:04")
		endStr, durStr := "——", "(running)"
		if entry.EndTime != "" {
			endT, _ := time.Parse(dtFmt, entry.EndTime)
			endStr = endT.Format("15:04")
			dur := endT.Sub(startT)
			h, m := int(dur.Hours()), int(dur.Minutes())%60
			durStr = fmt.Sprintf("%dh %02dm", h, m)
		}

		editBtn := widget.NewButton("Edit", func() {
			a.showEditDialog(entry, func() {
				a.window.SetContent(a.buildHistoryView())
			})
		})
		delBtn := widget.NewButton("Del", func() {
			dialog.ShowConfirm("Delete Entry", "Delete this entry? This cannot be undone.", func(ok bool) {
				if !ok {
					return
				}
				if entry.ID == a.runningID {
					a.stopTicker()
					a.runningID = 0
					a.descEntry.SetText("")
					a.projectEntry.SetText("")
					a.startStopBtn.SetText("▶  Start")
					a.clockLabel.Hide()
					a.discardBtn.Hide()
				}
				DeleteLog(entry.ID)
				a.window.SetContent(a.buildHistoryView())
			}, a.window)
		})

		row := container.NewHBox(
			widget.NewLabel(dateStr),
			widget.NewLabel(startStr),
			widget.NewLabel(endStr),
			widget.NewLabel(durStr),
			widget.NewLabel(entry.Description),
			widget.NewLabel(entry.Project),
			widget.NewSeparator(),
			editBtn,
			delBtn,
		)
		vbox.Add(row)
		vbox.Add(widget.NewSeparator())
	}

	return container.NewBorder(
		container.NewVBox(backBtn, widget.NewSeparator()),
		nil, nil, nil,
		container.NewVScroll(vbox),
	)
}

func (a *App) showEditDialog(entry LogEntry, onSave func()) {
	startT, _ := time.Parse(dtFmt, entry.StartTime)

	dateEntry := widget.NewEntry()
	dateEntry.SetText(startT.Format("2006-01-02"))

	startEntry := widget.NewEntry()
	startEntry.SetText(startT.Format("15:04"))

	endEntry := widget.NewEntry()
	endEntry.SetPlaceHolder("leave blank if still running")
	if entry.EndTime != "" {
		endT, _ := time.Parse(dtFmt, entry.EndTime)
		endEntry.SetText(endT.Format("15:04"))
	}

	descEntry := widget.NewEntry()
	descEntry.SetText(entry.Description)

	projEntry := widget.NewEntry()
	projEntry.SetText(entry.Project)

	items := []*widget.FormItem{
		widget.NewFormItem("Date (YYYY-MM-DD)", dateEntry),
		widget.NewFormItem("Start (HH:MM)", startEntry),
		widget.NewFormItem("End (HH:MM)", endEntry),
		widget.NewFormItem("Description", descEntry),
		widget.NewFormItem("Project", projEntry),
	}

	dialog.ShowForm("Edit Entry", "Save", "Cancel", items, func(save bool) {
		if !save {
			return
		}
		startISO := dateEntry.Text + "T" + startEntry.Text + ":00"
		if _, err := time.Parse(dtFmt, startISO); err != nil {
			dialog.ShowError(fmt.Errorf("invalid start — use YYYY-MM-DD and HH:MM"), a.window)
			return
		}
		var endISO string
		if endEntry.Text != "" {
			endISO = dateEntry.Text + "T" + endEntry.Text + ":00"
			if _, err := time.Parse(dtFmt, endISO); err != nil {
				dialog.ShowError(fmt.Errorf("invalid end time — use HH:MM"), a.window)
				return
			}
			if endISO <= startISO {
				dialog.ShowError(fmt.Errorf("end time must be after start time"), a.window)
				return
			}
		}
		UpdateLog(entry.ID, startISO, endISO, descEntry.Text, projEntry.Text)
		a.refreshProjects()
		onSave()
	}, a.window)
}
```

- [ ] **Step 3: Build and manually test the history view**

```powershell
go build -o LedgerTimer.exe .
./LedgerTimer.exe
```

Start a timer, stop it. Click History → Show History. Verify the entry appears. Click Edit — change the description. Click Save. Verify the change persists. Click Del — confirm the prompt removes the entry.

- [ ] **Step 4: Commit**

```bash
git add go/ui.go
git commit -m "feat(go): add history view with edit and delete"
```

---

### Task 8: Export view

**Files:**
- Modify: `go/ui.go`

- [ ] **Step 1: Remove the export stub**

Remove:
```go
func (a *App) buildExportView() fyne.CanvasObject { return widget.NewLabel("Export coming soon") }
```

- [ ] **Step 2: Add `buildExportView`**

```go
func (a *App) buildExportView() fyne.CanvasObject {
	fromEntry := widget.NewEntry()
	fromEntry.SetText(firstOfMonth())

	toEntry := widget.NewEntry()
	toEntry.SetText(lastOfMonth())

	statusLabel := widget.NewLabel("")

	exportBtn := widget.NewButton("Export to CSV", func() {
		from := fromEntry.Text
		to := toEntry.Text

		if _, err := time.Parse("2006-01-02", from); err != nil {
			dialog.ShowError(fmt.Errorf("invalid From date — use YYYY-MM-DD"), a.window)
			return
		}
		if _, err := time.Parse("2006-01-02", to); err != nil {
			dialog.ShowError(fmt.Errorf("invalid To date — use YYYY-MM-DD"), a.window)
			return
		}
		if from > to {
			dialog.ShowError(fmt.Errorf("From date must be on or before To date"), a.window)
			return
		}

		fd := dialog.NewFileSave(func(w fyne.URIWriteCloser, err error) {
			if w == nil || err != nil {
				return
			}
			defer w.Close()
			rows, _ := GetLogsForExport(from, to)
			count, err := ExportToCSV(rows, w)
			if err != nil {
				dialog.ShowError(err, a.window)
				return
			}
			statusLabel.SetText(fmt.Sprintf("✓ Exported %d entries.", count))
		}, a.window)
		fd.SetFileName(fmt.Sprintf("LedgerTimer_%s.csv", from[:7]))
		fd.Show()
	})

	backBtn := widget.NewButton("← Back", func() {
		a.window.SetContent(a.timerContent)
	})

	content := container.NewVBox(
		widget.NewForm(
			widget.NewFormItem("From (YYYY-MM-DD)", fromEntry),
			widget.NewFormItem("To (YYYY-MM-DD)", toEntry),
		),
		exportBtn,
		statusLabel,
	)

	return container.NewBorder(
		container.NewVBox(backBtn, widget.NewSeparator()),
		nil, nil, nil,
		content,
	)
}
```

- [ ] **Step 3: Run the full test suite**

```powershell
go test ./...
```

Expected: All tests PASS.

- [ ] **Step 4: Build and manually test the export flow**

```powershell
go build -o LedgerTimer.exe .
./LedgerTimer.exe
```

Start and stop a timer. Click Export → Export to CSV. Set the date range. Click Export to CSV. A save-file dialog opens. Save the file. Status shows "✓ Exported N entries." Open the CSV and verify the columns match: `Date, Start Time, End Time, Duration, Description, Project`.

- [ ] **Step 5: Commit**

```bash
git add go/ui.go
git commit -m "feat(go): add export view with file save dialog"
```

---

### Task 9: Build Windows exe and final verification

**Files:** No new source files — build output only.

- [ ] **Step 1: Run all tests one final time**

```powershell
go test ./...
```

Expected: All PASS.

- [ ] **Step 2: Build the Windows executable without a console window**

```powershell
go build -ldflags="-H windowsgui" -o LedgerTimer.exe .
```

Expected: `go/LedgerTimer.exe` created. No console window when launched.

- [ ] **Step 3: Smoke-test the exe**

Launch `./LedgerTimer.exe` and verify:
1. Window opens with menu bar (File / History / Export).
2. Start timer → clock ticks every second.
3. Stop timer → entry appears in History view.
4. Edit the entry → changes saved.
5. Export to CSV → file opens with correct columns and decimal duration.
6. Close and reopen → any previously running timer resumes automatically.

- [ ] **Step 4: Reference build commands for macOS and Linux** (must be run on those platforms)

**macOS** (run on a Mac):
```bash
cd go
go build -o LedgerTimer .
# Optional .app bundle:
go install fyne.io/fyne/v2/cmd/fyne@latest
fyne package -os darwin -icon ../assets/app_icon.png
```

**Linux** (run on Linux; install `gcc libgl1-mesa-dev xorg-dev` first):
```bash
cd go
go build -o LedgerTimer .
# Optional desktop package:
fyne package -os linux -icon ../assets/app_icon.png
```

- [ ] **Step 5: Commit**

```bash
git add go/
git commit -m "feat(go): Go/Fyne LedgerTimer v1 — cross-platform desktop time tracker"
```
