package collector

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func testRequester(server *httptest.Server) *Requester {
	return &Requester{Client: server.Client(), Limiter: NewRateLimiter(0), MaxAttempts: 3, BaseDelay: time.Millisecond}
}

func TestGitHubPlatformParsesFixture(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("q") != "context is:issue" {
			t.Fatalf("unexpected query: %s", r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"items":[{"html_url":"https://github.test/1","title":"Need context","body":"Detailed body","user":{"login":"dev"},"labels":[{"name":"feature"}]}]}`))
	}))
	defer server.Close()
	platform := &GitHubPlatform{Requester: testRequester(server), Endpoint: server.URL}

	items, err := platform.Collect(context.Background(), "context", 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 || items[0].Author != "dev" || items[0].Tags[0] != "feature" {
		t.Fatalf("unexpected items: %#v", items)
	}
}

func TestGitHubPlatformPaginatesToMaxItems(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		page := r.URL.Query().Get("page")
		count := 100
		if page == "2" {
			count = 1
		}
		items := make([]map[string]any, 0, count)
		for index := 0; index < count; index++ {
			id := (requests-1)*100 + index + 1
			items = append(items, map[string]any{
				"html_url": fmt.Sprintf("https://github.test/%d", id), "title": fmt.Sprintf("Issue %d", id),
				"body": "Body", "user": map[string]string{"login": "dev"}, "labels": []any{},
			})
		}
		json.NewEncoder(w).Encode(map[string]any{"items": items})
	}))
	defer server.Close()
	platform := &GitHubPlatform{Requester: testRequester(server), Endpoint: server.URL}

	items, err := platform.Collect(context.Background(), "context", 101)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 101 || requests != 2 || items[100].SourceURL != "https://github.test/101" {
		t.Fatalf("requests=%d items=%d last=%#v", requests, len(items), items[len(items)-1])
	}
}

func TestStackOverflowPlatformParsesFixture(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"items":[{"question_id":42,"title":"Context &amp; cancellation","body":"<p>Detailed body</p>","tags":["go"],"owner":{"display_name":"Ada"}}]}`))
	}))
	defer server.Close()
	platform := &StackOverflowPlatform{Requester: testRequester(server), Endpoint: server.URL}

	items, err := platform.Collect(context.Background(), "context", 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 || items[0].Title != "Context & cancellation" || items[0].Content != "Detailed body" {
		t.Fatalf("unexpected items: %#v", items)
	}
}

func TestStackOverflowPlatformFollowsHasMore(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		id := requests
		json.NewEncoder(w).Encode(map[string]any{
			"items":    []map[string]any{{"question_id": id, "title": fmt.Sprintf("Question %d", id)}},
			"has_more": requests == 1,
		})
	}))
	defer server.Close()
	platform := &StackOverflowPlatform{Requester: testRequester(server), Endpoint: server.URL}

	items, err := platform.Collect(context.Background(), "context", 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 2 || requests != 2 || items[1].SourceURL != "https://stackoverflow.com/questions/2" {
		t.Fatalf("requests=%d items=%#v", requests, items)
	}
}

func TestJuejinPlatformParsesFixture(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"data":[{"result_model":{"article_info":{"article_id":"abc","title":"上下文","brief_content":"详细内容"},"author_user_info":{"user_name":"作者"},"tags":[{"tag_name":"Go"}]}}]}`))
	}))
	defer server.Close()
	platform := &JuejinPlatform{Requester: testRequester(server), Endpoint: server.URL}

	items, err := platform.Collect(context.Background(), "上下文", 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 || items[0].SourceURL != "https://juejin.cn/post/abc" || items[0].Tags[0] != "Go" {
		t.Fatalf("unexpected items: %#v", items)
	}
}

func TestJuejinPlatformFollowsCursor(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		w.Header().Set("Content-Type", "application/json")
		if requests == 1 {
			if request["cursor"] != "0" {
				t.Fatalf("unexpected first cursor: %v", request["cursor"])
			}
			w.Write([]byte(`{"data":[{"result_model":{"article_info":{"article_id":"1","title":"First"}}}],"cursor":"next","has_more":true}`))
			return
		}
		if request["cursor"] != "next" {
			t.Fatalf("unexpected second cursor: %v", request["cursor"])
		}
		w.Write([]byte(`{"data":[{"result_model":{"article_info":{"article_id":"2","title":"Second"}}}],"cursor":"","has_more":false}`))
	}))
	defer server.Close()
	platform := &JuejinPlatform{Requester: testRequester(server), Endpoint: server.URL}

	items, err := platform.Collect(context.Background(), "context", 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 2 || requests != 2 || items[1].SourceURL != "https://juejin.cn/post/2" {
		t.Fatalf("requests=%d items=%#v", requests, items)
	}
}
