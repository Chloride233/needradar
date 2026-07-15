package collector

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type Server struct {
	service *Service
	logger  *log.Logger
	handler http.Handler
}

type createTasksRequest struct {
	Keyword   string           `json:"keyword"`
	Platforms []string         `json:"platforms"`
	MaxItems  int              `json:"max_items"`
	TaskIDs   map[string]int64 `json:"task_ids"`
}

func NewServer(service *Service, logger *log.Logger) *Server {
	server := &Server{service: service, logger: logger}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", server.health)
	mux.HandleFunc("GET /metrics", server.metrics)
	mux.HandleFunc("POST /v1/tasks", server.createTasks)
	mux.HandleFunc("/v1/tasks/", server.taskRoute)
	server.handler = server.logging(mux)
	return server
}

func (s *Server) Handler() http.Handler { return s.handler }

func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "needradar-collector", "version": "0.1.0", "platforms": s.service.Platforms()})
}

func (s *Server) metrics(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, s.service.MetricsSnapshot())
}

func (s *Server) createTasks(w http.ResponseWriter, r *http.Request) {
	var request createTasksRequest
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&request); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON: "+err.Error())
		return
	}
	tasks, err := s.service.CreateTasks(request.Keyword, request.Platforms, request.MaxItems, request.TaskIDs)
	if err != nil {
		status := http.StatusBadRequest
		if strings.Contains(err.Error(), "already exists") {
			status = http.StatusConflict
		}
		writeError(w, status, err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{"items": tasks, "total": len(tasks)})
}

func (s *Server) taskRoute(w http.ResponseWriter, r *http.Request) {
	remainder := strings.Trim(strings.TrimPrefix(r.URL.Path, "/v1/tasks/"), "/")
	parts := strings.Split(remainder, "/")
	if len(parts) == 0 || parts[0] == "" {
		writeError(w, http.StatusNotFound, "task not found")
		return
	}
	id, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid task id")
		return
	}
	if len(parts) == 1 && r.Method == http.MethodGet {
		task, ok := s.service.Task(id)
		if !ok {
			writeError(w, http.StatusNotFound, "task not found")
			return
		}
		writeJSON(w, http.StatusOK, task)
		return
	}
	if len(parts) != 2 {
		writeError(w, http.StatusNotFound, "route not found")
		return
	}
	switch {
	case parts[1] == "retry" && r.Method == http.MethodPost:
		task, err := s.service.Retry(id)
		s.writeTaskResult(w, task, err)
	case parts[1] == "cancel" && r.Method == http.MethodPost:
		task, err := s.service.Cancel(id)
		s.writeTaskResult(w, task, err)
	case parts[1] == "events" && r.Method == http.MethodGet:
		s.events(w, r, id)
	default:
		writeError(w, http.StatusNotFound, "route not found")
	}
}

func (s *Server) writeTaskResult(w http.ResponseWriter, task Task, err error) {
	if err == nil {
		writeJSON(w, http.StatusOK, task)
		return
	}
	status := http.StatusConflict
	if err.Error() == "task not found" {
		status = http.StatusNotFound
	}
	writeError(w, status, err.Error())
}

func (s *Server) events(w http.ResponseWriter, r *http.Request, id int64) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, "streaming unsupported")
		return
	}
	history, events, cancel, terminal, err := s.service.Subscribe(id)
	if err != nil {
		writeError(w, http.StatusNotFound, err.Error())
		return
	}
	defer cancel()
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	for _, event := range history {
		writeSSE(w, event)
	}
	flusher.Flush()
	if terminal {
		return
	}
	for {
		select {
		case <-r.Context().Done():
			return
		case event := <-events:
			writeSSE(w, event)
			flusher.Flush()
			if event.Status == StatusCompleted || event.Status == StatusFailed {
				return
			}
		}
	}
}

func (s *Server) logging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		if s.logger == nil {
			return
		}
		entry, _ := json.Marshal(map[string]any{"event": "http_request", "method": r.Method, "path": r.URL.Path, "duration_ms": time.Since(started).Milliseconds()})
		s.logger.Print(string(entry))
	})
}

func writeSSE(w http.ResponseWriter, event Event) {
	payload, _ := json.Marshal(event)
	fmt.Fprintf(w, "id: %d\nevent: %s\ndata: %s\n\n", event.Sequence, event.Type, payload)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(value)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}
