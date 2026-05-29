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
