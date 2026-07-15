package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"

	"needradar/collector-go/internal/collector"
)

func main() {
	logger := log.New(os.Stdout, "", 0)
	client := &http.Client{Timeout: durationEnv("COLLECTOR_REQUEST_TIMEOUT", 30*time.Second)}
	retries := &atomic.Int64{}
	endpoints := collector.DefaultEndpoints()
	if value := os.Getenv("COLLECTOR_GITHUB_URL"); value != "" {
		endpoints.GitHub = value
	}
	if value := os.Getenv("COLLECTOR_STACKOVERFLOW_URL"); value != "" {
		endpoints.StackOverflow = value
	}
	if value := os.Getenv("COLLECTOR_JUEJIN_URL"); value != "" {
		endpoints.Juejin = value
	}
	platforms := collector.NewPlatforms(
		client, endpoints, durationEnv("COLLECTOR_RATE_LIMIT", 500*time.Millisecond), retries,
		os.Getenv("GITHUB_TOKEN"), os.Getenv("STACKEXCHANGE_KEY"),
	)
	service := collector.NewService(collector.ServiceConfig{
		Concurrency: intEnv("COLLECTOR_CONCURRENCY", 4), QueueSize: intEnv("COLLECTOR_QUEUE_SIZE", 100), UpstreamRetries: retries,
	}, platforms)
	defer service.Close()

	server := &http.Server{
		Addr: os.Getenv("COLLECTOR_ADDR"), Handler: collector.NewServer(service, logger).Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	if server.Addr == "" {
		server.Addr = "127.0.0.1:8910"
	}
	go func() {
		logger.Printf(`{"event":"collector_started","address":%q}`, server.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal(err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	server.Shutdown(ctx)
}

func intEnv(name string, fallback int) int {
	value, err := strconv.Atoi(os.Getenv(name))
	if err != nil || value < 1 {
		return fallback
	}
	return value
}

func durationEnv(name string, fallback time.Duration) time.Duration {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	parsed, err := time.ParseDuration(value)
	if err != nil {
		return fallback
	}
	return parsed
}
