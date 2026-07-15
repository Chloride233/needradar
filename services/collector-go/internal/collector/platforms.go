package collector

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"sync/atomic"
	"time"
)

type Endpoints struct {
	GitHub        string
	StackOverflow string
	Juejin        string
}

func DefaultEndpoints() Endpoints {
	return Endpoints{
		GitHub:        "https://api.github.com/search/issues",
		StackOverflow: "https://api.stackexchange.com/2.3/search/excerpts",
		Juejin:        "https://api.juejin.cn/search_api/v1/search",
	}
}

type GitHubPlatform struct {
	Requester *Requester
	Endpoint  string
	Token     string
}

func (p *GitHubPlatform) Name() string { return "github" }

func (p *GitHubPlatform) Collect(ctx context.Context, keyword string, maxItems int) ([]Discussion, error) {
	headers := map[string]string{"Accept": "application/vnd.github+json"}
	if p.Token != "" {
		headers["Authorization"] = "Bearer " + p.Token
	}
	items := make([]Discussion, 0, maxItems)
	perPage := min(maxItems, 100)
	for page := 1; len(items) < maxItems; page++ {
		query := url.Values{}
		query.Set("q", keyword+" is:issue")
		query.Set("sort", "updated")
		query.Set("order", "desc")
		query.Set("per_page", strconv.Itoa(perPage))
		query.Set("page", strconv.Itoa(page))
		resp, err := p.Requester.Do(ctx, http.MethodGet, p.Endpoint+"?"+query.Encode(), nil, headers)
		if err != nil {
			return nil, err
		}
		var payload struct {
			Items []struct {
				URL   string `json:"html_url"`
				Title string `json:"title"`
				Body  string `json:"body"`
				User  struct {
					Login string `json:"login"`
				} `json:"user"`
				Labels []struct {
					Name string `json:"name"`
				} `json:"labels"`
			} `json:"items"`
		}
		decodeErr := json.NewDecoder(io.LimitReader(resp.Body, 8<<20)).Decode(&payload)
		resp.Body.Close()
		if decodeErr != nil {
			return nil, fmt.Errorf("parse github response: %w", decodeErr)
		}
		for _, issue := range payload.Items {
			tags := make([]string, 0, len(issue.Labels))
			for _, label := range issue.Labels {
				tags = append(tags, label.Name)
			}
			items = append(items, Discussion{Platform: p.Name(), SourceURL: issue.URL, Title: issue.Title, Content: issue.Body, Author: issue.User.Login, Tags: tags})
			if len(items) == maxItems {
				break
			}
		}
		if len(payload.Items) < perPage {
			break
		}
	}
	return items, nil
}

type StackOverflowPlatform struct {
	Requester *Requester
	Endpoint  string
	Key       string
}

func (p *StackOverflowPlatform) Name() string { return "stackoverflow" }

func (p *StackOverflowPlatform) Collect(ctx context.Context, keyword string, maxItems int) ([]Discussion, error) {
	items := make([]Discussion, 0, maxItems)
	pageSize := min(maxItems, 100)
	for page := 1; len(items) < maxItems; page++ {
		query := url.Values{}
		query.Set("order", "desc")
		query.Set("sort", "relevance")
		query.Set("q", keyword)
		query.Set("site", "stackoverflow")
		query.Set("pagesize", strconv.Itoa(pageSize))
		query.Set("page", strconv.Itoa(page))
		query.Set("filter", "default")
		if p.Key != "" {
			query.Set("key", p.Key)
		}
		resp, err := p.Requester.Do(ctx, http.MethodGet, p.Endpoint+"?"+query.Encode(), nil, nil)
		if err != nil {
			return nil, err
		}
		var payload struct {
			Items []struct {
				QuestionID int64    `json:"question_id"`
				Title      string   `json:"title"`
				Body       string   `json:"body"`
				Tags       []string `json:"tags"`
				Owner      struct {
					DisplayName string `json:"display_name"`
				} `json:"owner"`
			} `json:"items"`
			HasMore bool `json:"has_more"`
		}
		decodeErr := json.NewDecoder(io.LimitReader(resp.Body, 8<<20)).Decode(&payload)
		resp.Body.Close()
		if decodeErr != nil {
			return nil, fmt.Errorf("parse stackoverflow response: %w", decodeErr)
		}
		for _, question := range payload.Items {
			items = append(items, Discussion{
				Platform: p.Name(), SourceURL: fmt.Sprintf("https://stackoverflow.com/questions/%d", question.QuestionID),
				Title: html.UnescapeString(question.Title), Content: stripHTML(question.Body), Author: question.Owner.DisplayName, Tags: question.Tags,
			})
			if len(items) == maxItems {
				break
			}
		}
		if !payload.HasMore || len(payload.Items) == 0 {
			break
		}
	}
	return items, nil
}

type JuejinPlatform struct {
	Requester *Requester
	Endpoint  string
}

func (p *JuejinPlatform) Name() string { return "juejin" }

func (p *JuejinPlatform) Collect(ctx context.Context, keyword string, maxItems int) ([]Discussion, error) {
	items := make([]Discussion, 0, maxItems)
	cursor := "0"
	for len(items) < maxItems {
		body, _ := json.Marshal(map[string]any{
			"key_word": keyword, "search_type": 0, "cursor": cursor, "limit": min(maxItems-len(items), 40),
		})
		resp, err := p.Requester.Do(ctx, http.MethodPost, p.Endpoint, body, map[string]string{
			"Content-Type": "application/json", "User-Agent": "NeedRadar/0.1.0",
		})
		if err != nil {
			return nil, err
		}
		var payload struct {
			Data    []json.RawMessage `json:"data"`
			Cursor  string            `json:"cursor"`
			HasMore bool              `json:"has_more"`
		}
		decodeErr := json.NewDecoder(io.LimitReader(resp.Body, 8<<20)).Decode(&payload)
		resp.Body.Close()
		if decodeErr != nil {
			return nil, fmt.Errorf("parse juejin response: %w", decodeErr)
		}
		for _, raw := range payload.Data {
			item, err := parseJuejinItem(raw)
			if err != nil {
				return nil, err
			}
			if item.SourceURL != "" {
				items = append(items, item)
			}
			if len(items) == maxItems {
				break
			}
		}
		if len(payload.Data) == 0 || !payload.HasMore || payload.Cursor == "" || payload.Cursor == "0" {
			break
		}
		cursor = payload.Cursor
	}
	return items, nil
}

func parseJuejinItem(raw json.RawMessage) (Discussion, error) {
	var entry map[string]any
	if err := json.Unmarshal(raw, &entry); err != nil {
		return Discussion{}, fmt.Errorf("parse juejin item: %w", err)
	}
	model := object(entry["result_model"])
	if len(model) == 0 {
		model = entry
	}
	article := object(model["article_info"])
	if len(article) == 0 {
		article = object(model["pin_info"])
	}
	id := text(article["article_id"])
	if id == "" {
		id = text(model["article_id"])
	}
	if id == "" {
		id = text(article["pin_id"])
	}
	author := object(model["author_user_info"])
	tags := []string{}
	if values, ok := model["tags"].([]any); ok {
		for _, value := range values {
			if name := text(object(value)["tag_name"]); name != "" {
				tags = append(tags, name)
			}
		}
	}
	content := text(article["brief_content"])
	if content == "" {
		content = text(article["content"])
	}
	return Discussion{Platform: "juejin", SourceURL: choose(id != "", "https://juejin.cn/post/"+id, ""), Title: text(article["title"]), Content: content, Author: text(author["user_name"]), Tags: tags}, nil
}

var htmlTags = regexp.MustCompile(`<[^>]+>`)

func stripHTML(value string) string { return html.UnescapeString(htmlTags.ReplaceAllString(value, "")) }

func object(value any) map[string]any {
	result, _ := value.(map[string]any)
	return result
}

func text(value any) string {
	result, _ := value.(string)
	return result
}

func choose(condition bool, yes, no string) string {
	if condition {
		return yes
	}
	return no
}

func NewPlatforms(client *http.Client, endpoints Endpoints, interval time.Duration, retries *atomic.Int64, githubToken, stackKey string) map[string]Platform {
	makeRequester := func() *Requester {
		return &Requester{Client: client, Limiter: NewRateLimiter(interval), MaxAttempts: 3, BaseDelay: 20 * time.Millisecond, RetryCounter: retries}
	}
	return map[string]Platform{
		"github":        &GitHubPlatform{Requester: makeRequester(), Endpoint: endpoints.GitHub, Token: githubToken},
		"stackoverflow": &StackOverflowPlatform{Requester: makeRequester(), Endpoint: endpoints.StackOverflow, Key: stackKey},
		"juejin":        &JuejinPlatform{Requester: makeRequester(), Endpoint: endpoints.Juejin},
	}
}
