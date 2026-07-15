package collector

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type RateLimiter struct {
	mu       sync.Mutex
	interval time.Duration
	next     time.Time
}

func NewRateLimiter(interval time.Duration) *RateLimiter {
	return &RateLimiter{interval: interval}
}

func (l *RateLimiter) Wait(ctx context.Context) error {
	if l.interval <= 0 {
		return nil
	}
	l.mu.Lock()
	now := time.Now()
	wait := l.next.Sub(now)
	if wait < 0 {
		wait = 0
	}
	l.next = now.Add(wait).Add(l.interval)
	l.mu.Unlock()

	if wait == 0 {
		return nil
	}
	timer := time.NewTimer(wait)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

type Requester struct {
	Client       *http.Client
	Limiter      *RateLimiter
	MaxAttempts  int
	BaseDelay    time.Duration
	RetryCounter *atomic.Int64
}

func (r *Requester) Do(ctx context.Context, method, rawURL string, body []byte, headers map[string]string) (*http.Response, error) {
	attempts := r.MaxAttempts
	if attempts <= 0 {
		attempts = 3
	}
	baseDelay := r.BaseDelay
	if baseDelay <= 0 {
		baseDelay = time.Second
	}
	client := r.Client
	if client == nil {
		client = &http.Client{Timeout: 30 * time.Second}
	}
	limiter := r.Limiter
	if limiter == nil {
		limiter = NewRateLimiter(0)
	}

	for attempt := 1; attempt <= attempts; attempt++ {
		if err := limiter.Wait(ctx); err != nil {
			return nil, err
		}
		req, err := http.NewRequestWithContext(ctx, method, rawURL, bytes.NewReader(body))
		if err != nil {
			return nil, err
		}
		for key, value := range headers {
			req.Header.Set(key, value)
		}
		resp, err := client.Do(req)
		if err == nil && resp.StatusCode < 400 {
			return resp, nil
		}
		if err == nil && !retryableStatus(resp.StatusCode) {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
			return nil, fmt.Errorf("upstream status %d", resp.StatusCode)
		}
		if err == nil {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
		if attempt == attempts {
			if err != nil {
				return nil, err
			}
			return nil, fmt.Errorf("upstream status %d", resp.StatusCode)
		}
		if r.RetryCounter != nil {
			r.RetryCounter.Add(1)
		}
		delay := baseDelay * time.Duration(1<<(attempt-1))
		if err == nil && resp.StatusCode == http.StatusTooManyRequests {
			delay = retryAfter(resp.Header.Get("Retry-After"), delay)
		}
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil, ctx.Err()
		case <-timer.C:
		}
	}
	return nil, fmt.Errorf("request attempts exhausted")
}

func retryableStatus(status int) bool {
	return status == http.StatusTooManyRequests || status >= 500
}

func retryAfter(value string, fallback time.Duration) time.Duration {
	value = strings.TrimSpace(value)
	if value == "" {
		return fallback
	}
	if seconds, err := strconv.Atoi(value); err == nil {
		if seconds < 0 {
			return 0
		}
		return time.Duration(seconds) * time.Second
	}
	if date, err := http.ParseTime(value); err == nil {
		if delay := time.Until(date); delay > 0 {
			return delay
		}
		return 0
	}
	return fallback
}
