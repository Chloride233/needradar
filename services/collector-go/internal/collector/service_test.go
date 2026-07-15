package collector

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"
)

type fakePlatform struct {
	name       string
	delay      time.Duration
	failFirst  atomic.Bool
	block      bool
	current    atomic.Int64
	maxCurrent atomic.Int64
	items      []Discussion
}

func (p *fakePlatform) Name() string { return p.name }

func (p *fakePlatform) Collect(ctx context.Context, _ string, _ int) ([]Discussion, error) {
	current := p.current.Add(1)
	defer p.current.Add(-1)
	for {
		maximum := p.maxCurrent.Load()
		if current <= maximum || p.maxCurrent.CompareAndSwap(maximum, current) {
			break
		}
	}
	if p.failFirst.CompareAndSwap(true, false) {
		return nil, errors.New("temporary failure")
	}
	if p.block {
		<-ctx.Done()
		return nil, ctx.Err()
	}
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-time.After(p.delay):
		return append([]Discussion(nil), p.items...), nil
	}
}

func waitTerminal(t *testing.T, service *Service, id int64) Task {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		task, ok := service.Task(id)
		if ok && (task.Status == StatusCompleted || task.Status == StatusFailed) {
			return task
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatalf("task %d did not become terminal", id)
	return Task{}
}

func TestWorkerPoolBoundsConcurrency(t *testing.T) {
	platform := &fakePlatform{name: "github", delay: 20 * time.Millisecond}
	service := NewService(ServiceConfig{Concurrency: 2, QueueSize: 20}, map[string]Platform{"github": platform})
	defer service.Close()
	tasks, err := service.CreateTasks("context", []string{"github", "github", "github", "github", "github", "github"}, 1, nil)
	if err != nil {
		t.Fatal(err)
	}
	for _, task := range tasks {
		waitTerminal(t, service, task.ID)
	}
	if maximum := platform.maxCurrent.Load(); maximum != 2 {
		t.Fatalf("expected max concurrency 2, got %d", maximum)
	}
}

func TestQueueUsesConfiguredCapacity(t *testing.T) {
	service := NewService(ServiceConfig{Concurrency: 2, QueueSize: 1}, map[string]Platform{
		"github": &fakePlatform{name: "github"},
	})
	defer service.Close()
	if capacity := cap(service.queue); capacity != 1 {
		t.Fatalf("expected queue capacity 1, got %d", capacity)
	}
}

func TestRetryReusesTaskID(t *testing.T) {
	platform := &fakePlatform{name: "github"}
	platform.failFirst.Store(true)
	service := NewService(ServiceConfig{Concurrency: 1, QueueSize: 2}, map[string]Platform{"github": platform})
	defer service.Close()
	tasks, _ := service.CreateTasks("context", []string{"github"}, 1, map[string]int64{"github": 77})
	if failed := waitTerminal(t, service, 77); failed.Status != StatusFailed {
		t.Fatalf("expected failure: %#v", failed)
	}
	retried, err := service.Retry(77)
	if err != nil || retried.ID != tasks[0].ID {
		t.Fatalf("retry=%#v err=%v", retried, err)
	}
	if completed := waitTerminal(t, service, 77); completed.Status != StatusCompleted || completed.Attempts != 2 {
		t.Fatalf("unexpected completed task: %#v", completed)
	}
}

func TestCreateTasksRejectsExistingIDAtomically(t *testing.T) {
	platforms := map[string]Platform{
		"github":        &fakePlatform{name: "github"},
		"stackoverflow": &fakePlatform{name: "stackoverflow"},
	}
	service := NewService(ServiceConfig{Concurrency: 1, QueueSize: 4}, platforms)
	defer service.Close()
	if _, err := service.CreateTasks("context", []string{"github"}, 1, map[string]int64{"github": 9}); err != nil {
		t.Fatal(err)
	}
	_, err := service.CreateTasks(
		"context",
		[]string{"stackoverflow", "github"},
		1,
		map[string]int64{"stackoverflow": 8, "github": 9},
	)
	if err == nil {
		t.Fatal("expected existing task ID error")
	}
	if _, exists := service.Task(8); exists {
		t.Fatal("batch inserted a task before rejecting the existing ID")
	}
}

func TestCancelRunningTask(t *testing.T) {
	platform := &fakePlatform{name: "github", block: true}
	service := NewService(ServiceConfig{Concurrency: 1, QueueSize: 2}, map[string]Platform{"github": platform})
	defer service.Close()
	tasks, _ := service.CreateTasks("context", []string{"github"}, 1, nil)
	for {
		task, _ := service.Task(tasks[0].ID)
		if task.Status == StatusRunning {
			break
		}
		time.Sleep(time.Millisecond)
	}
	if _, err := service.Cancel(tasks[0].ID); err != nil {
		t.Fatal(err)
	}
	cancelled := waitTerminal(t, service, tasks[0].ID)
	if cancelled.ErrorMessage != "cancelled" {
		t.Fatalf("unexpected cancellation: %#v", cancelled)
	}
}

func TestDeduplicateURLAndFingerprint(t *testing.T) {
	items := []Discussion{
		{SourceURL: "https://example.test/a?utm_source=x", Title: "Title", Content: "Same body"},
		{SourceURL: "https://example.test/a", Title: "Other", Content: "Other body"},
		{SourceURL: "https://example.test/b", Title: " title ", Content: "same   body"},
		{SourceURL: "https://example.test/c", Title: "Unique", Content: "Body"},
	}
	unique, skipped := deduplicate(items)
	if len(unique) != 2 || skipped != 2 {
		t.Fatalf("unique=%#v skipped=%d", unique, skipped)
	}
}

func TestSubscribeIncludesTerminalHistory(t *testing.T) {
	service := NewService(ServiceConfig{Concurrency: 1, QueueSize: 2}, map[string]Platform{"github": &fakePlatform{name: "github"}})
	defer service.Close()
	tasks, _ := service.CreateTasks("context", []string{"github"}, 1, nil)
	waitTerminal(t, service, tasks[0].ID)
	history, _, cancel, terminal, err := service.Subscribe(tasks[0].ID)
	defer cancel()
	if err != nil || !terminal || history[len(history)-1].Type != "completed" {
		t.Fatalf("history=%#v terminal=%v err=%v", history, terminal, err)
	}
}
