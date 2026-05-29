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
