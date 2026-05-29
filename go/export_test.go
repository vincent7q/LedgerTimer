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
	if _, err := ExportToCSV(nil, &buf); err != nil {
		t.Fatal(err)
	}
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
	if _, err := ExportToCSV(rows, &buf); err != nil {
		t.Fatal(err)
	}
	r := csv.NewReader(strings.NewReader(buf.String()))
	if _, err := r.Read(); err != nil { // skip header
		t.Fatal(err)
	}
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
	if _, err := ExportToCSV(rows, &buf); err != nil {
		t.Fatal(err)
	}
	r := csv.NewReader(strings.NewReader(buf.String()))
	if _, err := r.Read(); err != nil { // skip header
		t.Fatal(err)
	}
	record, err := r.Read()
	if err != nil {
		t.Fatal(err)
	}
	if record[3] != "1.50" {
		t.Errorf("duration: want 1.50, got %s", record[3])
	}
}

func TestExportEmptyDescriptionAndProject(t *testing.T) {
	rows := []LogEntry{
		{StartTime: "2026-05-26T09:00:00", EndTime: "2026-05-26T09:30:00"},
	}
	var buf bytes.Buffer
	if _, err := ExportToCSV(rows, &buf); err != nil {
		t.Fatal(err)
	}
	r := csv.NewReader(strings.NewReader(buf.String()))
	if _, err := r.Read(); err != nil { // skip header
		t.Fatal(err)
	}
	record, err := r.Read()
	if err != nil {
		t.Fatal(err)
	}
	if record[4] != "" || record[5] != "" {
		t.Errorf("want empty description and project, got %q %q", record[4], record[5])
	}
}
