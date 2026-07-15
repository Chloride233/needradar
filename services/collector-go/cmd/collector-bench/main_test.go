package main

import (
	"testing"
	"time"
)

func testWorkload(taskCount int) *workload {
	tasks := make([]workloadTask, taskCount)
	for index := range tasks {
		id := int64(index + 1)
		tasks[index] = workloadTask{ID: id, SubmissionIndex: index, RetryFirst: id%10 == 0}
	}
	return &workload{
		SchemaVersion: 1,
		Seed:          20260715,
		TaskCount:     taskCount,
		ItemsPerTask:  10,
		Payload: workloadPayload{
			SourceURLTemplate: "https://fake.test/task-{task_id:06d}/item-{item_index:02d}",
			TitleTemplate:     "NeedRadar task {task_id:06d} item {item_index:02d}",
			ContentTemplate:   "deterministic collector payload task {task_id:06d} item {item_index:02d}",
		},
		Tasks: tasks,
	}
}

func TestRunBenchmarkScenarios(t *testing.T) {
	for _, scenario := range []string{"normal", "retry_10pct", "duplicate_10pct"} {
		t.Run(scenario, func(t *testing.T) {
			result, err := runBenchmark(testWorkload(20), scenario, 20, 4, 100*time.Microsecond)
			if err != nil {
				t.Fatal(err)
			}
			if result.CompletedTasks != 20 || result.FailedTasks != 0 {
				t.Fatalf("unexpected task counts: %+v", result)
			}
			expectedRetries := int64(0)
			expectedDuplicates := 0
			if scenario == "retry_10pct" {
				expectedRetries = 2
			}
			if scenario == "duplicate_10pct" {
				expectedDuplicates = 20
			}
			if result.RetryAttempts != expectedRetries || result.DuplicateCount != expectedDuplicates {
				t.Fatalf("unexpected scenario counts: %+v", result)
			}
		})
	}
}

func TestValidateWorkloadRejectsChangedRetryDistribution(t *testing.T) {
	value := testWorkload(20)
	value.Tasks[9].RetryFirst = false
	if err := validateWorkload(value); err == nil {
		t.Fatal("expected changed retry distribution to fail")
	}
}

func TestRenderItemsUsesUniqueURLAndDuplicateFingerprint(t *testing.T) {
	items, err := renderItems(testWorkload(20), 1, "duplicate_10pct")
	if err != nil {
		t.Fatal(err)
	}
	if items[0].SourceURL == items[9].SourceURL {
		t.Fatal("duplicate scenario must retain distinct URLs")
	}
	if items[0].Title != items[9].Title || items[0].Content != items[9].Content {
		t.Fatal("duplicate scenario must repeat the normalized fingerprint payload")
	}
	if items[0].SourceURL != "https://fake.test/task-000001/item-00" ||
		items[0].Title != "NeedRadar task 000001 item 00" ||
		items[0].Content != "deterministic collector payload task 000001 item 00" {
		t.Fatalf("first payload does not match the shared workload: %+v", items[0])
	}
	if items[9].SourceURL != "https://fake.test/task-000001/item-09" {
		t.Fatalf("duplicate URL does not match the shared workload: %s", items[9].SourceURL)
	}
}
