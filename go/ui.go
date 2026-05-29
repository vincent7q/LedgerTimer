package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/lxn/walk"
	. "github.com/lxn/walk/declarative"
)

// App holds the main window and timer state.
type App struct {
	mw *walk.MainWindow

	projectCB    *walk.ComboBox
	descLE       *walk.LineEdit
	startStopBtn *walk.PushButton
	clockLB      *walk.Label

	runningID    int64
	runningStart time.Time
	tickerDone   chan struct{}
}

func (a *App) run() error {
	err := MainWindow{
		AssignTo: &a.mw,
		Title:    "LedgerTimer",
		MinSize:  Size{Width: 380, Height: 170},
		Size:     Size{Width: 420, Height: 190},
		Layout:   VBox{},
		MenuItems: []MenuItem{
			Menu{
				Text: "&File",
				Items: []MenuItem{
					Action{Text: "E&xit", OnTriggered: func() { a.mw.Close() }},
				},
			},
			Action{Text: "&History", OnTriggered: a.showHistory},
			Action{Text: "&Export", OnTriggered: a.showExport},
		},
		Children: []Widget{
			Composite{
				Layout: Grid{Columns: 2},
				Children: []Widget{
					Label{Text: "Project:"},
					ComboBox{AssignTo: &a.projectCB, Editable: true},
					Label{Text: "Description:"},
					LineEdit{AssignTo: &a.descLE},
				},
			},
			PushButton{AssignTo: &a.startStopBtn, Text: "Start", OnClicked: a.toggleTimer},
			Label{
				AssignTo: &a.clockLB,
				Text:     "",
				Font:     Font{Family: "Segoe UI", PointSize: 18, Bold: true},
			},
		},
	}.Create()
	if err != nil {
		return err
	}

	a.refreshProjects()
	a.descLE.TextChanged().Attach(a.syncRunning)
	a.restoreRunningState()

	a.mw.Run()
	return nil
}

// --- timer logic ---

func (a *App) toggleTimer() {
	if a.runningID == 0 {
		a.startTimer()
	} else {
		a.stopTimer()
	}
}

func (a *App) startTimer() {
	start := time.Now().Format(dtFmt)
	id, err := StartTimer(start, a.descLE.Text(), a.projectCB.Text())
	if err != nil {
		a.errBox(err)
		return
	}
	a.runningID = id
	a.runningStart, _ = time.Parse(dtFmt, start)
	a.startStopBtn.SetText("Stop")
	a.startTicker()
	a.refreshProjects()
}

func (a *App) stopTimer() {
	end := time.Now().Format(dtFmt)
	// Persist final description/project together with the end time.
	if err := UpdateLog(a.runningID, a.runningStart.Format(dtFmt), end, a.descLE.Text(), a.projectCB.Text()); err != nil {
		a.errBox(err)
		return
	}
	a.resetTimerUI()
	a.refreshProjects()
}

// resetTimerUI stops the ticker and returns the main window to its idle state.
func (a *App) resetTimerUI() {
	a.stopTicker()
	a.runningID = 0
	a.descLE.SetText("")
	a.projectCB.SetText("")
	a.startStopBtn.SetText("Start")
	a.clockLB.SetText("")
}

// syncRunning writes the live description to the running row so an unexpected
// shutdown still keeps what was typed. Project is captured at start and stop.
func (a *App) syncRunning() {
	if a.runningID != 0 {
		UpdateLog(a.runningID, a.runningStart.Format(dtFmt), "", a.descLE.Text(), a.projectCB.Text())
	}
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
				text := fmt.Sprintf("%02d:%02d:%02d", h, m, s)
				a.mw.Synchronize(func() { a.clockLB.SetText(text) })
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
	a.descLE.SetText(entry.Description)
	a.projectCB.SetText(entry.Project)
	a.startStopBtn.SetText("Stop")
	a.startTicker()
}

func (a *App) refreshProjects() {
	projects, _ := GetDistinctProjects()
	cur := a.projectCB.Text()
	a.projectCB.SetModel(projects)
	a.projectCB.SetText(cur)
}

func (a *App) errBox(err error) {
	walk.MsgBox(a.mw, "Error", err.Error(), walk.MsgBoxIconError)
}

// --- history dialog ---

// logModel feeds GetAllLogs() rows into a walk TableView.
type logModel struct {
	walk.TableModelBase
	items []LogEntry
}

func (m *logModel) RowCount() int { return len(m.items) }

func (m *logModel) Value(row, col int) interface{} {
	e := m.items[row]
	start, _ := time.Parse(dtFmt, e.StartTime)
	switch col {
	case 0:
		return start.Format("2006-01-02")
	case 1:
		return start.Format("15:04")
	case 2:
		if e.EndTime == "" {
			return "—"
		}
		end, _ := time.Parse(dtFmt, e.EndTime)
		return end.Format("15:04")
	case 3:
		if e.EndTime == "" {
			return "(running)"
		}
		end, _ := time.Parse(dtFmt, e.EndTime)
		d := end.Sub(start)
		return fmt.Sprintf("%dh %02dm", int(d.Hours()), int(d.Minutes())%60)
	case 4:
		return e.Description
	case 5:
		return e.Project
	}
	return ""
}

func (a *App) showHistory() {
	model := &logModel{}
	reload := func() {
		logs, err := GetAllLogs()
		if err != nil {
			a.errBox(err)
			return
		}
		model.items = logs
		model.PublishRowsReset()
	}
	reload()

	var dlg *walk.Dialog
	var tv *walk.TableView

	editSelected := func() {
		i := tv.CurrentIndex()
		if i < 0 || i >= len(model.items) {
			return
		}
		if a.showEditDialog(dlg, model.items[i]) {
			reload()
		}
	}
	deleteSelected := func() {
		i := tv.CurrentIndex()
		if i < 0 || i >= len(model.items) {
			return
		}
		entry := model.items[i]
		if walk.MsgBox(dlg, "Delete Entry", "Delete this entry? This cannot be undone.",
			walk.MsgBoxYesNo|walk.MsgBoxIconQuestion) != walk.DlgCmdYes {
			return
		}
		if entry.ID == a.runningID {
			a.resetTimerUI()
		}
		if err := DeleteLog(entry.ID); err != nil {
			a.errBox(err)
			return
		}
		reload()
	}

	Dialog{
		AssignTo: &dlg,
		Title:    "History",
		MinSize:  Size{Width: 720, Height: 420},
		Layout:   VBox{},
		Children: []Widget{
			TableView{
				AssignTo:         &tv,
				Model:            model,
				ColumnsOrderable: true,
				OnItemActivated:  func() { editSelected() },
				Columns: []TableViewColumn{
					{Title: "Date", Width: 90},
					{Title: "Start", Width: 60},
					{Title: "End", Width: 60},
					{Title: "Duration", Width: 90},
					{Title: "Description", Width: 240},
					{Title: "Project", Width: 130},
				},
			},
			Composite{
				Layout: HBox{},
				Children: []Widget{
					PushButton{Text: "Edit", OnClicked: editSelected},
					PushButton{Text: "Delete", OnClicked: deleteSelected},
					HSpacer{},
					PushButton{Text: "Close", OnClicked: func() { dlg.Accept() }},
				},
			},
		},
	}.Run(a.mw)
}

// showEditDialog edits one entry. Returns true if the user saved a valid change.
func (a *App) showEditDialog(owner walk.Form, e LogEntry) bool {
	start, _ := time.Parse(dtFmt, e.StartTime)
	endStr := ""
	if e.EndTime != "" {
		end, _ := time.Parse(dtFmt, e.EndTime)
		endStr = end.Format("15:04")
	}

	var dlg *walk.Dialog
	var dateLE, startLE, endLE, descLE, projLE *walk.LineEdit
	saved := false

	Dialog{
		AssignTo: &dlg,
		Title:    "Edit Entry",
		MinSize:  Size{Width: 320, Height: 240},
		Layout:   VBox{},
		Children: []Widget{
			Composite{
				Layout: Grid{Columns: 2},
				Children: []Widget{
					Label{Text: "Date (YYYY-MM-DD):"},
					LineEdit{AssignTo: &dateLE, Text: start.Format("2006-01-02")},
					Label{Text: "Start (HH:MM):"},
					LineEdit{AssignTo: &startLE, Text: start.Format("15:04")},
					Label{Text: "End (HH:MM):"},
					LineEdit{AssignTo: &endLE, Text: endStr, CueBanner: "blank if running"},
					Label{Text: "Description:"},
					LineEdit{AssignTo: &descLE, Text: e.Description},
					Label{Text: "Project:"},
					LineEdit{AssignTo: &projLE, Text: e.Project},
				},
			},
			Composite{
				Layout: HBox{},
				Children: []Widget{
					HSpacer{},
					PushButton{
						Text: "Save",
						OnClicked: func() {
							startISO := dateLE.Text() + "T" + startLE.Text() + ":00"
							if _, err := time.Parse(dtFmt, startISO); err != nil {
								walk.MsgBox(dlg, "Invalid", "Start must be YYYY-MM-DD and HH:MM.", walk.MsgBoxIconWarning)
								return
							}
							var endISO string
							if strings.TrimSpace(endLE.Text()) != "" {
								endISO = dateLE.Text() + "T" + endLE.Text() + ":00"
								if _, err := time.Parse(dtFmt, endISO); err != nil {
									walk.MsgBox(dlg, "Invalid", "End must be HH:MM.", walk.MsgBoxIconWarning)
									return
								}
								if endISO <= startISO {
									walk.MsgBox(dlg, "Invalid", "End time must be after start time.", walk.MsgBoxIconWarning)
									return
								}
							}
							if err := UpdateLog(e.ID, startISO, endISO, descLE.Text(), projLE.Text()); err != nil {
								a.errBox(err)
								return
							}
							// If this was the running entry and an end was set, stop tracking it.
							if e.ID == a.runningID && endISO != "" {
								a.resetTimerUI()
							}
							a.refreshProjects()
							saved = true
							dlg.Accept()
						},
					},
					PushButton{Text: "Cancel", OnClicked: func() { dlg.Cancel() }},
				},
			},
		},
	}.Run(owner)

	return saved
}

// --- export dialog ---

func (a *App) showExport() {
	var dlg *walk.Dialog
	var fromLE, toLE *walk.LineEdit

	Dialog{
		AssignTo: &dlg,
		Title:    "Export to CSV",
		MinSize:  Size{Width: 340, Height: 150},
		Layout:   VBox{},
		Children: []Widget{
			Composite{
				Layout: Grid{Columns: 2},
				Children: []Widget{
					Label{Text: "From (YYYY-MM-DD):"},
					LineEdit{AssignTo: &fromLE, Text: firstOfMonth()},
					Label{Text: "To (YYYY-MM-DD):"},
					LineEdit{AssignTo: &toLE, Text: lastOfMonth()},
				},
			},
			Composite{
				Layout: HBox{},
				Children: []Widget{
					HSpacer{},
					PushButton{Text: "Export…", OnClicked: func() { a.doExport(dlg, fromLE.Text(), toLE.Text()) }},
					PushButton{Text: "Cancel", OnClicked: func() { dlg.Cancel() }},
				},
			},
		},
	}.Run(a.mw)
}

func (a *App) doExport(owner walk.Form, from, to string) {
	if _, err := time.Parse("2006-01-02", from); err != nil {
		walk.MsgBox(owner, "Invalid", "From date must be YYYY-MM-DD.", walk.MsgBoxIconWarning)
		return
	}
	if _, err := time.Parse("2006-01-02", to); err != nil {
		walk.MsgBox(owner, "Invalid", "To date must be YYYY-MM-DD.", walk.MsgBoxIconWarning)
		return
	}
	if from > to {
		walk.MsgBox(owner, "Invalid", "From date must be on or before To date.", walk.MsgBoxIconWarning)
		return
	}

	save := walk.FileDialog{
		Title:    "Save CSV",
		Filter:   "CSV Files (*.csv)|*.csv|All Files (*.*)|*.*",
		FilePath: fmt.Sprintf("LedgerTimer_%s.csv", from[:7]),
	}
	ok, err := save.ShowSave(owner)
	if err != nil {
		a.errBox(err)
		return
	}
	if !ok {
		return
	}
	path := save.FilePath
	if !strings.HasSuffix(strings.ToLower(path), ".csv") {
		path += ".csv"
	}

	f, err := os.Create(path)
	if err != nil {
		a.errBox(err)
		return
	}
	defer f.Close()

	rows, err := GetLogsForExport(from, to)
	if err != nil {
		a.errBox(err)
		return
	}
	count, err := ExportToCSV(rows, f)
	if err != nil {
		a.errBox(err)
		return
	}
	walk.MsgBox(owner, "Export Complete", fmt.Sprintf("Exported %d entries.", count), walk.MsgBoxIconInformation)
}

// --- date helpers ---

func firstOfMonth() string {
	now := time.Now()
	return time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.Local).Format("2006-01-02")
}

func lastOfMonth() string {
	now := time.Now()
	first := time.Date(now.Year(), now.Month()+1, 1, 0, 0, 0, 0, time.Local)
	return first.AddDate(0, 0, -1).Format("2006-01-02")
}
