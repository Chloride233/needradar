package collector

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"net/url"
	"runtime"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type ServiceConfig struct {
	Concurrency     int
	QueueSize       int
	UpstreamRetries *atomic.Int64
}

type Metrics struct {
	TasksCreated   atomic.Int64
	TasksCompleted atomic.Int64
	TasksFailed    atomic.Int64
	TasksCancelled atomic.Int64
	TasksRunning   atomic.Int64
}

type taskState struct {
	mu          sync.RWMutex
	task        Task
	ctx         context.Context
	cancel      context.CancelFunc
	maxItems    int
	events      []Event
	subscribers map[chan Event]struct{}
}

type Service struct {
	ctx             context.Context
	cancel          context.CancelFunc
	platforms       map[string]Platform
	queue           chan int64
	tasksMu         sync.RWMutex
	tasks           map[int64]*taskState
	nextID          atomic.Int64
	eventSeq        atomic.Int64
	metrics         Metrics
	upstreamRetries *atomic.Int64
	wg              sync.WaitGroup
}

func NewService(config ServiceConfig, platforms map[string]Platform) *Service {
	if config.Concurrency < 1 {
		config.Concurrency = 4
	}
	if config.QueueSize < 1 {
		config.QueueSize = 100
	}
	ctx, cancel := context.WithCancel(context.Background())
	service := &Service{
		ctx: ctx, cancel: cancel, platforms: platforms,
		queue: make(chan int64, config.QueueSize), tasks: map[int64]*taskState{}, upstreamRetries: config.UpstreamRetries,
	}
	for worker := 0; worker < config.Concurrency; worker++ {
		service.wg.Add(1)
		go service.worker()
	}
	return service
}

func (s *Service) Close() {
	s.cancel()
	s.wg.Wait()
}

func (s *Service) Platforms() []string {
	names := make([]string, 0, len(s.platforms))
	for name := range s.platforms {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func (s *Service) CreateTasks(keyword string, platforms []string, maxItems int, requestedIDs map[string]int64) ([]Task, error) {
	keyword = strings.TrimSpace(keyword)
	if keyword == "" {
		return nil, errors.New("keyword is required")
	}
	if len(platforms) == 0 {
		return nil, errors.New("at least one platform is required")
	}
	if maxItems < 1 {
		maxItems = 100
	}
	requested := map[int64]struct{}{}
	for _, platform := range platforms {
		if _, ok := s.platforms[platform]; !ok {
			return nil, fmt.Errorf("unsupported platform: %s", platform)
		}
		if id := requestedIDs[platform]; id > 0 {
			if _, duplicate := requested[id]; duplicate {
				return nil, fmt.Errorf("duplicate requested task id: %d", id)
			}
			requested[id] = struct{}{}
		}
	}

	states := make([]*taskState, 0, len(platforms))
	s.tasksMu.Lock()
	for id := range requested {
		if _, exists := s.tasks[id]; exists {
			s.tasksMu.Unlock()
			return nil, fmt.Errorf("task %d already exists", id)
		}
	}
	for _, platform := range platforms {
		id := requestedIDs[platform]
		if id <= 0 {
			id = s.nextID.Add(1)
		} else {
			for {
				current := s.nextID.Load()
				if id <= current || s.nextID.CompareAndSwap(current, id) {
					break
				}
			}
		}
		ctx, cancel := context.WithCancel(s.ctx)
		now := time.Now().UTC()
		state := &taskState{
			task: Task{ID: id, Keyword: keyword, Platform: platform, Status: StatusPending, FilterMode: "off", CreatedAt: now, UpdatedAt: now},
			ctx:  ctx, cancel: cancel, maxItems: maxItems, subscribers: map[chan Event]struct{}{},
		}
		s.tasks[id] = state
		states = append(states, state)
	}
	s.tasksMu.Unlock()

	result := make([]Task, 0, len(states))
	for _, state := range states {
		state.mu.Lock()
		s.emitLocked(state, "queued", "task queued")
		result = append(result, publicTask(state.task))
		state.mu.Unlock()
		s.metrics.TasksCreated.Add(1)
		select {
		case <-s.ctx.Done():
			return nil, errors.New("service stopped")
		case s.queue <- state.task.ID:
		}
	}
	return result, nil
}

func (s *Service) Task(id int64) (Task, bool) {
	state, ok := s.state(id)
	if !ok {
		return Task{}, false
	}
	state.mu.RLock()
	defer state.mu.RUnlock()
	return publicTask(state.task), true
}

func (s *Service) Retry(id int64) (Task, error) {
	state, ok := s.state(id)
	if !ok {
		return Task{}, errors.New("task not found")
	}
	state.mu.Lock()
	if state.task.Status != StatusFailed {
		state.mu.Unlock()
		return Task{}, errors.New("only failed tasks can be retried")
	}
	state.cancel()
	state.ctx, state.cancel = context.WithCancel(s.ctx)
	state.task.Status = StatusPending
	state.task.ErrorMessage = ""
	state.task.TotalItems = 0
	state.task.NewItems = 0
	state.task.SkippedItems = 0
	state.task.Items = nil
	state.task.UpdatedAt = time.Now().UTC()
	s.emitLocked(state, "retry_queued", "failed task requeued")
	task := publicTask(state.task)
	state.mu.Unlock()
	select {
	case <-s.ctx.Done():
		return Task{}, errors.New("service stopped")
	case s.queue <- id:
		return task, nil
	}
}

func (s *Service) Cancel(id int64) (Task, error) {
	state, ok := s.state(id)
	if !ok {
		return Task{}, errors.New("task not found")
	}
	state.mu.Lock()
	defer state.mu.Unlock()
	if state.task.Status == StatusCompleted || state.task.Status == StatusFailed {
		return Task{}, errors.New("task is already terminal")
	}
	state.cancel()
	if state.task.Status == StatusPending {
		state.task.Status = StatusFailed
		state.task.ErrorMessage = "cancelled"
		state.task.UpdatedAt = time.Now().UTC()
		s.metrics.TasksCancelled.Add(1)
		s.metrics.TasksFailed.Add(1)
		s.emitLocked(state, "cancelled", "task cancelled")
	}
	return publicTask(state.task), nil
}

func (s *Service) Subscribe(id int64) ([]Event, <-chan Event, func(), bool, error) {
	state, ok := s.state(id)
	if !ok {
		return nil, nil, nil, false, errors.New("task not found")
	}
	state.mu.Lock()
	defer state.mu.Unlock()
	history := append([]Event(nil), state.events...)
	terminal := state.task.Status == StatusCompleted || state.task.Status == StatusFailed
	channel := make(chan Event, 32)
	if !terminal {
		state.subscribers[channel] = struct{}{}
	}
	cancel := func() {
		state.mu.Lock()
		delete(state.subscribers, channel)
		state.mu.Unlock()
	}
	return history, channel, cancel, terminal, nil
}

func (s *Service) MetricsSnapshot() map[string]any {
	var memory runtime.MemStats
	runtime.ReadMemStats(&memory)
	s.tasksMu.RLock()
	tasks := len(s.tasks)
	s.tasksMu.RUnlock()
	upstreamRetries := int64(0)
	if s.upstreamRetries != nil {
		upstreamRetries = s.upstreamRetries.Load()
	}
	return map[string]any{
		"tasks": tasks, "tasks_created": s.metrics.TasksCreated.Load(),
		"tasks_completed": s.metrics.TasksCompleted.Load(), "tasks_failed": s.metrics.TasksFailed.Load(),
		"tasks_cancelled": s.metrics.TasksCancelled.Load(), "tasks_running": s.metrics.TasksRunning.Load(),
		"upstream_retries": upstreamRetries, "goroutines": runtime.NumGoroutine(),
		"alloc_bytes": memory.Alloc, "queue_depth": len(s.queue), "queue_capacity": cap(s.queue),
	}
}

func (s *Service) worker() {
	defer s.wg.Done()
	for {
		select {
		case <-s.ctx.Done():
			return
		case id := <-s.queue:
			s.execute(id)
		}
	}
}

func (s *Service) execute(id int64) {
	state, ok := s.state(id)
	if !ok {
		return
	}
	state.mu.Lock()
	if state.task.Status != StatusPending {
		state.mu.Unlock()
		return
	}
	maxItems := state.maxItems
	state.task.Status = StatusRunning
	state.task.Attempts++
	state.task.UpdatedAt = time.Now().UTC()
	s.emitLocked(state, "running", "collection started")
	ctx := state.ctx
	platform := s.platforms[state.task.Platform]
	keyword := state.task.Keyword
	state.mu.Unlock()
	s.metrics.TasksRunning.Add(1)

	items, err := platform.Collect(ctx, keyword, maxItems)
	s.metrics.TasksRunning.Add(-1)
	state.mu.Lock()
	defer state.mu.Unlock()
	if err != nil {
		state.task.Status = StatusFailed
		if errors.Is(err, context.Canceled) {
			state.task.ErrorMessage = "cancelled"
			s.metrics.TasksCancelled.Add(1)
			s.emitLocked(state, "cancelled", "task cancelled")
		} else {
			state.task.ErrorMessage = err.Error()
			s.emitLocked(state, "failed", err.Error())
		}
		state.task.UpdatedAt = time.Now().UTC()
		s.metrics.TasksFailed.Add(1)
		return
	}
	unique, skipped := deduplicate(items)
	state.task.Status = StatusCompleted
	state.task.TotalItems = len(items)
	state.task.NewItems = len(unique)
	state.task.SkippedItems = skipped
	state.task.Items = unique
	state.task.UpdatedAt = time.Now().UTC()
	s.metrics.TasksCompleted.Add(1)
	s.emitLocked(state, "completed", fmt.Sprintf("collected %d unique items", len(unique)))
}

func (s *Service) state(id int64) (*taskState, bool) {
	s.tasksMu.RLock()
	defer s.tasksMu.RUnlock()
	state, ok := s.tasks[id]
	return state, ok
}

func (s *Service) emitLocked(state *taskState, eventType, message string) {
	event := Event{Sequence: s.eventSeq.Add(1), TaskID: state.task.ID, Type: eventType, Status: state.task.Status, Message: message, Timestamp: time.Now().UTC()}
	state.events = append(state.events, event)
	if len(state.events) > 100 {
		state.events = append([]Event(nil), state.events[len(state.events)-100:]...)
	}
	for subscriber := range state.subscribers {
		select {
		case subscriber <- event:
		default:
		}
	}
}

func publicTask(task Task) Task {
	copy := task
	copy.Items = append([]Discussion(nil), task.Items...)
	return copy
}

func deduplicate(items []Discussion) ([]Discussion, int) {
	result := make([]Discussion, 0, len(items))
	urls := map[string]struct{}{}
	fingerprints := map[string]struct{}{}
	for _, item := range items {
		normalizedURL := normalizeURL(item.SourceURL)
		fingerprint := contentFingerprint(item)
		if _, exists := urls[normalizedURL]; normalizedURL != "" && exists {
			continue
		}
		if _, exists := fingerprints[fingerprint]; exists {
			continue
		}
		if normalizedURL != "" {
			urls[normalizedURL] = struct{}{}
		}
		fingerprints[fingerprint] = struct{}{}
		result = append(result, item)
	}
	return result, len(items) - len(result)
}

func normalizeURL(raw string) string {
	parsed, err := url.Parse(strings.TrimSpace(raw))
	if err != nil {
		return strings.TrimSpace(raw)
	}
	parsed.Scheme = strings.ToLower(parsed.Scheme)
	parsed.Host = strings.ToLower(parsed.Host)
	parsed.Fragment = ""
	query := parsed.Query()
	for key := range query {
		lower := strings.ToLower(key)
		if strings.HasPrefix(lower, "utm_") || lower == "fbclid" || lower == "gclid" {
			query.Del(key)
		}
	}
	parsed.RawQuery = query.Encode()
	return parsed.String()
}

func contentFingerprint(item Discussion) string {
	normalized := strings.ToLower(strings.Join(strings.Fields(item.Title+"\n"+item.Content), " "))
	sum := sha256.Sum256([]byte(normalized))
	return hex.EncodeToString(sum[:])
}
