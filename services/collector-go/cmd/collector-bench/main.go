package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"needradar/collector-go/internal/collector"
)

var scenarios = map[string]struct{}{
	"normal": {}, "retry_10pct": {}, "duplicate_10pct": {},
}

type workloadTask struct {
	ID              int64 `json:"id"`
	SubmissionIndex int   `json:"submission_index"`
	RetryFirst      bool  `json:"retry_first"`
}

type workloadPayload struct {
	SourceURLTemplate string `json:"source_url_template"`
	TitleTemplate     string `json:"title_template"`
	ContentTemplate   string `json:"content_template"`
}

type workload struct {
	SchemaVersion int             `json:"schema_version"`
	Seed          int             `json:"seed"`
	TaskCount     int             `json:"task_count"`
	ItemsPerTask  int             `json:"items_per_task"`
	Payload       workloadPayload `json:"payload"`
	Tasks         []workloadTask  `json:"tasks"`
}

type fakeTransport struct {
	delay    time.Duration
	scenario string
	tasks    map[int64]workloadTask
	mu       sync.Mutex
	attempts map[int64]int
}

func (t *fakeTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	taskID, err := strconv.ParseInt(request.URL.Path[strings.LastIndex(request.URL.Path, "/")+1:], 10, 64)
	if err != nil {
		return nil, fmt.Errorf("invalid fake request task ID: %w", err)
	}
	timer := time.NewTimer(t.delay)
	defer timer.Stop()
	select {
	case <-request.Context().Done():
		return nil, request.Context().Err()
	case <-timer.C:
	}
	t.mu.Lock()
	t.attempts[taskID]++
	attempt := t.attempts[taskID]
	task, ok := t.tasks[taskID]
	t.mu.Unlock()
	if !ok {
		return nil, fmt.Errorf("unknown fake task ID: %d", taskID)
	}
	status := http.StatusOK
	if t.scenario == "retry_10pct" && task.RetryFirst && attempt == 1 {
		status = http.StatusServiceUnavailable
	}
	return &http.Response{
		StatusCode: status,
		Header:     make(http.Header),
		Body:       io.NopCloser(strings.NewReader("{}")),
		Request:    request,
	}, nil
}

type benchmarkPlatform struct {
	requester   *collector.Requester
	workload    *workload
	scenario    string
	release     <-chan struct{}
	ready       atomic.Int64
	readyTarget int64
	readySignal chan<- struct{}
	readyOnce   sync.Once
}

func (p *benchmarkPlatform) Name() string { return "benchmark" }

func (p *benchmarkPlatform) Collect(ctx context.Context, keyword string, _ int) ([]collector.Discussion, error) {
	taskID, err := strconv.ParseInt(keyword, 10, 64)
	if err != nil {
		return nil, fmt.Errorf("invalid benchmark keyword: %w", err)
	}
	if p.ready.Add(1) == p.readyTarget {
		p.readyOnce.Do(func() { close(p.readySignal) })
	}
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-p.release:
	}
	response, err := p.requester.Do(
		ctx,
		http.MethodGet,
		fmt.Sprintf("https://fake.test/request/%d", taskID),
		nil,
		nil,
	)
	if err != nil {
		return nil, err
	}
	response.Body.Close()
	return renderItems(p.workload, taskID, p.scenario)
}

type benchmarkResult struct {
	Implementation           string  `json:"implementation"`
	Scenario                 string  `json:"scenario"`
	TaskCount                int     `json:"task_count"`
	Concurrency              int     `json:"concurrency"`
	FakeLatencyMS            float64 `json:"fake_latency_ms"`
	RetryBackoffMS           float64 `json:"retry_backoff_ms"`
	MaxAttempts              int     `json:"max_attempts"`
	ItemsPerTask             int     `json:"items_per_task"`
	WallSeconds              float64 `json:"wall_seconds"`
	ThroughputTasksPerSecond float64 `json:"throughput_tasks_per_second"`
	P50LatencyMS             float64 `json:"p50_latency_ms"`
	P95LatencyMS             float64 `json:"p95_latency_ms"`
	P99LatencyMS             float64 `json:"p99_latency_ms"`
	CompletedTasks           int     `json:"completed_tasks"`
	FailedTasks              int     `json:"failed_tasks"`
	RetryAttempts            int64   `json:"retry_attempts"`
	DuplicateCount           int     `json:"duplicate_count"`
	UniqueResultCount        int     `json:"unique_result_count"`
	GoVersion                string  `json:"go_version"`
	Architecture             string  `json:"architecture"`
	GoMaxProcs               int     `json:"gomaxprocs"`
}

type subscription struct {
	id      int64
	history []collector.Event
	events  <-chan collector.Event
	cancel  func()
}

func main() {
	workloadPath := flag.String("workload", "", "path to the frozen JSON workload")
	scenario := flag.String("scenario", "", "normal, retry_10pct, or duplicate_10pct")
	taskCount := flag.Int("tasks", 0, "number of ordered workload tasks")
	concurrency := flag.Int("concurrency", 0, "worker count")
	flag.Parse()

	loaded, err := loadWorkload(*workloadPath)
	if err != nil {
		exitError(err)
	}
	result, err := runBenchmark(loaded, *scenario, *taskCount, *concurrency, 5*time.Millisecond)
	if err != nil {
		exitError(err)
	}
	encoder := json.NewEncoder(os.Stdout)
	if err := encoder.Encode(result); err != nil {
		exitError(err)
	}
}

func loadWorkload(path string) (*workload, error) {
	if path == "" {
		return nil, errors.New("workload path is required")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var value workload
	if err := json.Unmarshal(data, &value); err != nil {
		return nil, err
	}
	if err := validateWorkload(&value); err != nil {
		return nil, err
	}
	return &value, nil
}

func validateWorkload(value *workload) error {
	if value.SchemaVersion != 1 {
		return errors.New("unsupported workload schema")
	}
	if value.TaskCount != len(value.Tasks) || value.ItemsPerTask < 2 {
		return errors.New("workload dimensions mismatch")
	}
	for index, task := range value.Tasks {
		expectedID := int64(index + 1)
		if task.ID != expectedID || task.SubmissionIndex != index || task.RetryFirst != (task.ID%10 == 0) {
			return fmt.Errorf("workload task %d is not frozen correctly", expectedID)
		}
	}
	if value.Payload.SourceURLTemplate == "" || value.Payload.TitleTemplate == "" || value.Payload.ContentTemplate == "" {
		return errors.New("workload payload templates are required")
	}
	return nil
}

func runBenchmark(value *workload, scenario string, taskCount, concurrency int, delay time.Duration) (benchmarkResult, error) {
	if _, ok := scenarios[scenario]; !ok {
		return benchmarkResult{}, fmt.Errorf("unsupported scenario: %s", scenario)
	}
	if taskCount < 1 || taskCount > value.TaskCount || concurrency < 1 {
		return benchmarkResult{}, errors.New("tasks and concurrency must be positive and tasks must fit the workload")
	}
	tasks := make(map[int64]workloadTask, taskCount)
	for _, task := range value.Tasks[:taskCount] {
		tasks[task.ID] = task
	}
	transport := &fakeTransport{delay: delay, scenario: scenario, tasks: tasks, attempts: map[int64]int{}}
	retries := &atomic.Int64{}
	release := make(chan struct{})
	ready := make(chan struct{})
	platform := &benchmarkPlatform{
		requester: &collector.Requester{
			Client: &http.Client{Transport: transport}, Limiter: collector.NewRateLimiter(0),
			MaxAttempts: 3, BaseDelay: time.Millisecond, RetryCounter: retries,
		},
		workload: value, scenario: scenario, release: release,
		readyTarget: int64(min(taskCount, concurrency)), readySignal: ready,
	}
	service := collector.NewService(
		collector.ServiceConfig{Concurrency: concurrency, QueueSize: taskCount},
		map[string]collector.Platform{"benchmark": platform},
	)
	released := false
	defer func() {
		if !released {
			close(release)
		}
		service.Close()
	}()

	created := make([]collector.Task, 0, taskCount)
	for _, task := range value.Tasks[:taskCount] {
		batch, err := service.CreateTasks(
			strconv.FormatInt(task.ID, 10),
			[]string{"benchmark"},
			value.ItemsPerTask,
			map[string]int64{"benchmark": task.ID},
		)
		if err != nil {
			return benchmarkResult{}, err
		}
		created = append(created, batch[0])
	}
	<-ready

	subscriptions := make([]subscription, 0, taskCount)
	for _, task := range created {
		history, events, cancel, terminal, err := service.Subscribe(task.ID)
		if err != nil {
			return benchmarkResult{}, err
		}
		if terminal {
			cancel()
			return benchmarkResult{}, fmt.Errorf("task %d completed before queue release", task.ID)
		}
		subscriptions = append(subscriptions, subscription{id: task.ID, history: history, events: events, cancel: cancel})
	}

	releaseTime := time.Now()
	close(release)
	released = true
	latencies := make([]float64, 0, taskCount)
	completed, failed, duplicates, unique := 0, 0, 0, 0
	for _, subscription := range subscriptions {
		if err := waitTerminalEvent(subscription.history, subscription.events); err != nil {
			subscription.cancel()
			return benchmarkResult{}, err
		}
		subscription.cancel()
		task, ok := service.Task(subscription.id)
		if !ok {
			return benchmarkResult{}, fmt.Errorf("task %d disappeared", subscription.id)
		}
		latencies = append(latencies, float64(task.UpdatedAt.Sub(releaseTime).Nanoseconds())/1e6)
		if task.Status == collector.StatusCompleted {
			completed++
		} else {
			failed++
		}
		duplicates += task.SkippedItems
		unique += task.NewItems
	}
	wall := time.Since(releaseTime)
	sort.Float64s(latencies)
	result := benchmarkResult{
		Implementation: "go", Scenario: scenario, TaskCount: taskCount, Concurrency: concurrency,
		FakeLatencyMS: float64(delay.Nanoseconds()) / 1e6, RetryBackoffMS: 1, MaxAttempts: 3,
		ItemsPerTask: value.ItemsPerTask, WallSeconds: wall.Seconds(),
		ThroughputTasksPerSecond: float64(taskCount) / wall.Seconds(),
		P50LatencyMS:             percentile(latencies, 0.50), P95LatencyMS: percentile(latencies, 0.95),
		P99LatencyMS: percentile(latencies, 0.99), CompletedTasks: completed, FailedTasks: failed,
		RetryAttempts: retries.Load(), DuplicateCount: duplicates, UniqueResultCount: unique,
		GoVersion: runtime.Version(), Architecture: runtime.GOARCH, GoMaxProcs: runtime.GOMAXPROCS(0),
	}
	if err := validateResult(value, result); err != nil {
		return benchmarkResult{}, err
	}
	return result, nil
}

func renderItems(value *workload, taskID int64, scenario string) ([]collector.Discussion, error) {
	items := make([]collector.Discussion, 0, value.ItemsPerTask)
	for index := 0; index < value.ItemsPerTask; index++ {
		contentIndex := index
		if scenario == "duplicate_10pct" && index == value.ItemsPerTask-1 {
			contentIndex = 0
		}
		items = append(items, collector.Discussion{
			Platform:  "benchmark",
			SourceURL: applyTemplate(value.Payload.SourceURLTemplate, taskID, index),
			Title:     applyTemplate(value.Payload.TitleTemplate, taskID, contentIndex),
			Content:   applyTemplate(value.Payload.ContentTemplate, taskID, contentIndex),
			Author:    "benchmark",
			Tags:      []string{"collector-comparison"},
		})
	}
	return items, nil
}

func applyTemplate(template string, taskID int64, itemIndex int) string {
	value := strings.ReplaceAll(template, "{task_id:06d}", fmt.Sprintf("%06d", taskID))
	return strings.ReplaceAll(value, "{item_index:02d}", fmt.Sprintf("%02d", itemIndex))
}

func waitTerminalEvent(history []collector.Event, events <-chan collector.Event) error {
	for _, event := range history {
		if event.Type == "completed" || event.Type == "failed" || event.Type == "cancelled" {
			return nil
		}
	}
	for event := range events {
		if event.Type == "completed" || event.Type == "failed" || event.Type == "cancelled" {
			return nil
		}
	}
	return errors.New("event subscription closed before terminal event")
}

func validateResult(value *workload, result benchmarkResult) error {
	expectedRetries := int64(0)
	if result.Scenario == "retry_10pct" {
		for _, task := range value.Tasks[:result.TaskCount] {
			if task.RetryFirst {
				expectedRetries++
			}
		}
	}
	expectedDuplicates := 0
	if result.Scenario == "duplicate_10pct" {
		expectedDuplicates = result.TaskCount
	}
	expectedUnique := result.TaskCount*value.ItemsPerTask - expectedDuplicates
	if result.CompletedTasks != result.TaskCount || result.FailedTasks != 0 ||
		result.RetryAttempts != expectedRetries || result.DuplicateCount != expectedDuplicates ||
		result.UniqueResultCount != expectedUnique {
		return fmt.Errorf("functional result mismatch: %+v", result)
	}
	return nil
}

func percentile(sortedValues []float64, quantile float64) float64 {
	if len(sortedValues) == 0 {
		return 0
	}
	return sortedValues[int(float64(len(sortedValues)-1)*quantile)]
}

func exitError(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(2)
}
