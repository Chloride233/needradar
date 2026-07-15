package collector

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return f(request)
}

func TestRequesterRetries429And5xx(t *testing.T) {
	var calls atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		call := calls.Add(1)
		switch call {
		case 1:
			w.Header().Set("Retry-After", "0")
			w.WriteHeader(http.StatusTooManyRequests)
		case 2:
			w.WriteHeader(http.StatusBadGateway)
		default:
			w.WriteHeader(http.StatusOK)
		}
	}))
	defer server.Close()
	retries := &atomic.Int64{}
	requester := &Requester{Client: server.Client(), Limiter: NewRateLimiter(0), MaxAttempts: 3, BaseDelay: time.Millisecond, RetryCounter: retries}

	response, err := requester.Do(context.Background(), http.MethodGet, server.URL, nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if calls.Load() != 3 || retries.Load() != 2 {
		t.Fatalf("calls=%d retries=%d", calls.Load(), retries.Load())
	}
}

func TestRequesterDoesNotRetryNonTransient4xx(t *testing.T) {
	var calls atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		w.WriteHeader(http.StatusBadRequest)
	}))
	defer server.Close()
	requester := &Requester{Client: server.Client(), MaxAttempts: 3, BaseDelay: time.Millisecond}

	if _, err := requester.Do(context.Background(), http.MethodGet, server.URL, nil, nil); err == nil {
		t.Fatal("expected upstream error")
	}
	if calls.Load() != 1 {
		t.Fatalf("expected one call, got %d", calls.Load())
	}
}

func TestRequesterRetriesTimeout(t *testing.T) {
	var calls atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		time.Sleep(30 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()
	requester := &Requester{Client: &http.Client{Timeout: 3 * time.Millisecond}, MaxAttempts: 3, BaseDelay: time.Millisecond}

	if _, err := requester.Do(context.Background(), http.MethodGet, server.URL, nil, nil); err == nil {
		t.Fatal("expected timeout")
	}
	if calls.Load() != 3 {
		t.Fatalf("expected three calls, got %d", calls.Load())
	}
}

func TestRequesterRetriesNetworkError(t *testing.T) {
	var calls atomic.Int64
	client := &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		if calls.Add(1) < 3 {
			return nil, errors.New("connection reset")
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(http.NoBody),
			Header:     make(http.Header),
		}, nil
	})}
	requester := &Requester{Client: client, MaxAttempts: 3, BaseDelay: time.Millisecond}

	response, err := requester.Do(context.Background(), http.MethodGet, "http://provider.test", nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if calls.Load() != 3 {
		t.Fatalf("expected three calls, got %d", calls.Load())
	}
}

func TestRateLimiterEnforcesInterval(t *testing.T) {
	limiter := NewRateLimiter(20 * time.Millisecond)
	ctx := context.Background()
	if err := limiter.Wait(ctx); err != nil {
		t.Fatal(err)
	}
	started := time.Now()
	if err := limiter.Wait(ctx); err != nil {
		t.Fatal(err)
	}
	if elapsed := time.Since(started); elapsed < 15*time.Millisecond {
		t.Fatalf("rate limiter waited only %s", elapsed)
	}
}

func TestRetryAfterSeconds(t *testing.T) {
	if delay := retryAfter("2", time.Millisecond); delay != 2*time.Second {
		t.Fatalf("unexpected Retry-After delay: %s", delay)
	}
}
