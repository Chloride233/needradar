package collector

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestServerHealthAndMetrics(t *testing.T) {
	service := NewService(ServiceConfig{Concurrency: 1, QueueSize: 2}, map[string]Platform{
		"github": &fakePlatform{name: "github"},
	})
	defer service.Close()
	server := httptest.NewServer(NewServer(service, nil).Handler())
	defer server.Close()

	for _, path := range []string{"/health", "/metrics"} {
		response, err := server.Client().Get(server.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		if response.StatusCode != http.StatusOK {
			t.Fatalf("%s returned %d", path, response.StatusCode)
		}
		response.Body.Close()
	}
}

func TestFakeProviderEndToEnd(t *testing.T) {
	provider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/github":
			fmt.Fprint(w, `{"items":[{"html_url":"https://github.test/1","title":"Need context","body":"Detailed body","user":{"login":"dev"},"labels":[{"name":"feature"}]}]}`)
		case "/stackoverflow":
			fmt.Fprint(w, `{"items":[{"question_id":42,"title":"Context &amp; cancellation","body":"<p>Detailed body</p>","tags":["go"],"owner":{"display_name":"Ada"}}]}`)
		case "/juejin":
			fmt.Fprint(w, `{"data":[{"result_model":{"article_info":{"article_id":"abc","title":"上下文","brief_content":"详细内容"},"author_user_info":{"user_name":"作者"},"tags":[{"tag_name":"Go"}]}}]}`)
		default:
			http.NotFound(w, r)
		}
	}))
	defer provider.Close()

	retries := &atomic.Int64{}
	platforms := NewPlatforms(provider.Client(), Endpoints{
		GitHub: provider.URL + "/github", StackOverflow: provider.URL + "/stackoverflow", Juejin: provider.URL + "/juejin",
	}, 0, retries, "", "")
	service := NewService(ServiceConfig{Concurrency: 2, QueueSize: 8, UpstreamRetries: retries}, platforms)
	defer service.Close()
	server := httptest.NewServer(NewServer(service, nil).Handler())
	defer server.Close()

	payload := []byte(`{"keyword":"context","platforms":["github","stackoverflow","juejin"],"max_items":5,"task_ids":{"github":101,"stackoverflow":102,"juejin":103}}`)
	response, err := server.Client().Post(server.URL+"/v1/tasks", "application/json", bytes.NewReader(payload))
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(response.Body)
		t.Fatalf("create returned %d: %s", response.StatusCode, body)
	}

	for _, id := range []int64{101, 102, 103} {
		task := waitHTTPTask(t, server, id)
		if task.Status != StatusCompleted || len(task.Items) != 1 || task.Attempts != 1 {
			t.Fatalf("unexpected task %d: %#v", id, task)
		}
		eventsResponse, err := server.Client().Get(fmt.Sprintf("%s/v1/tasks/%d/events", server.URL, id))
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(eventsResponse.Body)
		eventsResponse.Body.Close()
		if !strings.Contains(string(body), "event: completed") {
			t.Fatalf("task %d SSE missing completion: %s", id, body)
		}
	}
}

func TestServerRetryAndCancel(t *testing.T) {
	failing := &fakePlatform{name: "github"}
	failing.failFirst.Store(true)
	blocking := &fakePlatform{name: "stackoverflow", block: true}
	service := NewService(ServiceConfig{Concurrency: 2, QueueSize: 4}, map[string]Platform{
		"github": failing, "stackoverflow": blocking,
	})
	defer service.Close()
	server := httptest.NewServer(NewServer(service, nil).Handler())
	defer server.Close()

	createHTTPTask(t, server, `{"keyword":"context","platforms":["github"],"task_ids":{"github":201}}`)
	if task := waitHTTPTask(t, server, 201); task.Status != StatusFailed {
		t.Fatalf("expected failed task: %#v", task)
	}
	postPath(t, server, "/v1/tasks/201/retry", http.StatusOK)
	if task := waitHTTPTask(t, server, 201); task.Status != StatusCompleted || task.Attempts != 2 {
		t.Fatalf("unexpected retried task: %#v", task)
	}

	createHTTPTask(t, server, `{"keyword":"context","platforms":["stackoverflow"],"task_ids":{"stackoverflow":202}}`)
	waitHTTPStatus(t, server, 202, StatusRunning)
	postPath(t, server, "/v1/tasks/202/cancel", http.StatusOK)
	if task := waitHTTPTask(t, server, 202); task.Status != StatusFailed || task.ErrorMessage != "cancelled" {
		t.Fatalf("unexpected cancelled task: %#v", task)
	}
}

func TestServerSSEStreamsLiveCompletion(t *testing.T) {
	release := make(chan struct{})
	platform := platformFunc{name: "github", collect: func(ctx context.Context, _ string, _ int) ([]Discussion, error) {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-release:
			return []Discussion{{Platform: "github", SourceURL: "https://github.test/live", Title: "Live", Content: "Done"}}, nil
		}
	}}
	service := NewService(ServiceConfig{Concurrency: 1, QueueSize: 2}, map[string]Platform{"github": platform})
	defer service.Close()
	server := httptest.NewServer(NewServer(service, nil).Handler())
	defer server.Close()
	createHTTPTask(t, server, `{"keyword":"context","platforms":["github"],"task_ids":{"github":301}}`)
	waitHTTPStatus(t, server, 301, StatusRunning)

	response, err := server.Client().Get(server.URL + "/v1/tasks/301/events")
	if err != nil {
		t.Fatal(err)
	}
	close(release)
	body, err := io.ReadAll(response.Body)
	response.Body.Close()
	if err != nil {
		t.Fatal(err)
	}
	text := string(body)
	if !strings.Contains(text, "event: running") || !strings.Contains(text, "event: completed") {
		t.Fatalf("unexpected SSE stream: %s", text)
	}
}

type platformFunc struct {
	name    string
	collect func(context.Context, string, int) ([]Discussion, error)
}

func (p platformFunc) Name() string { return p.name }

func (p platformFunc) Collect(ctx context.Context, keyword string, maxItems int) ([]Discussion, error) {
	return p.collect(ctx, keyword, maxItems)
}

func createHTTPTask(t *testing.T, server *httptest.Server, body string) {
	t.Helper()
	response, err := server.Client().Post(server.URL+"/v1/tasks", "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusCreated {
		payload, _ := io.ReadAll(response.Body)
		t.Fatalf("create returned %d: %s", response.StatusCode, payload)
	}
}

func postPath(t *testing.T, server *httptest.Server, path string, expected int) {
	t.Helper()
	response, err := server.Client().Post(server.URL+path, "application/json", nil)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != expected {
		t.Fatalf("%s returned %d", path, response.StatusCode)
	}
}

func waitHTTPTask(t *testing.T, server *httptest.Server, id int64) Task {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		task := getHTTPTask(t, server, id)
		if task.Status == StatusCompleted || task.Status == StatusFailed {
			return task
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatalf("task %d did not become terminal", id)
	return Task{}
}

func waitHTTPStatus(t *testing.T, server *httptest.Server, id int64, status TaskStatus) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if getHTTPTask(t, server, id).Status == status {
			return
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatalf("task %d did not reach %s", id, status)
}

func getHTTPTask(t *testing.T, server *httptest.Server, id int64) Task {
	t.Helper()
	response, err := server.Client().Get(fmt.Sprintf("%s/v1/tasks/%d", server.URL, id))
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var task Task
	if err := json.NewDecoder(response.Body).Decode(&task); err != nil {
		t.Fatal(err)
	}
	return task
}
