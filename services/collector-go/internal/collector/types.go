package collector

import (
	"context"
	"time"
)

type Discussion struct {
	Platform  string   `json:"platform"`
	SourceURL string   `json:"source_url"`
	Title     string   `json:"title"`
	Content   string   `json:"content"`
	Author    string   `json:"author"`
	Tags      []string `json:"tags"`
}

type Platform interface {
	Name() string
	Collect(ctx context.Context, keyword string, maxItems int) ([]Discussion, error)
}

type TaskStatus string

const (
	StatusPending   TaskStatus = "pending"
	StatusRunning   TaskStatus = "running"
	StatusCompleted TaskStatus = "completed"
	StatusFailed    TaskStatus = "failed"
)

type Task struct {
	ID             int64        `json:"id"`
	Keyword        string       `json:"keyword"`
	Platform       string       `json:"platform"`
	Status         TaskStatus   `json:"status"`
	TotalItems     int          `json:"total_items"`
	NewItems       int          `json:"new_items"`
	SkippedItems   int          `json:"skipped_items"`
	NoiseCount     int          `json:"noise_count"`
	ExtractedCount int          `json:"extracted_count"`
	FilterMode     string       `json:"filter_mode"`
	ErrorMessage   string       `json:"error_message,omitempty"`
	ReportPath     string       `json:"report_path,omitempty"`
	Attempts       int          `json:"attempts"`
	Items          []Discussion `json:"items,omitempty"`
	CreatedAt      time.Time    `json:"created_at"`
	UpdatedAt      time.Time    `json:"updated_at"`
}

type Event struct {
	Sequence  int64      `json:"sequence"`
	TaskID    int64      `json:"task_id"`
	Type      string     `json:"type"`
	Status    TaskStatus `json:"status"`
	Message   string     `json:"message,omitempty"`
	Timestamp time.Time  `json:"timestamp"`
}
