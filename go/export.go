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
