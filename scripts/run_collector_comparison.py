#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
import subprocess
import sys
import time
from pathlib import Path

from needradar.services.collector_comparison import (
    IMPLEMENTATIONS,
    SCENARIOS,
    build_report,
    build_workload,
    canonical_json,
    load_jsonl,
    pretty_json,
    render_report_markdown,
    sha256_bytes,
    sha256_file,
    validate_records,
    validate_report_provenance,
    validate_result,
    validate_startup_records,
    validate_workload,
)

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation" / "phase4"
WORKLOAD_PATH = EVALUATION / "collector-comparison-workload.json"
MANIFEST_PATH = EVALUATION / "collector-comparison-manifest.json"
RUNS_PATH = EVALUATION / "collector-comparison-runs.jsonl"
STARTUP_RUNS_PATH = EVALUATION / "collector-comparison-startup-runs.jsonl"
REPORT_JSON_PATH = EVALUATION / "collector-comparison.json"
REPORT_MARKDOWN_PATH = EVALUATION / "collector-comparison.md"
GO_DIR = ROOT / "services" / "collector-go"
GO_BINARY = Path("/private/tmp/needradar-collector-bench")
PYTHON_RUNNER = ROOT / "scripts" / "collector_benchmark_python.py"
GO_RUNNER = GO_DIR / "cmd" / "collector-bench" / "main.go"
ORCHESTRATOR = Path(__file__).resolve()
SEED = 20260715

SOURCE_PATHS = {
    "python_contract": ROOT / "src" / "needradar" / "services" / "collector_comparison.py",
    "python_runner": PYTHON_RUNNER,
    "python_orchestrator": ORCHESTRATOR,
    "python_scheduler": ROOT / "src" / "needradar" / "services" / "collector_scheduler.py",
    "python_retry": ROOT / "src" / "needradar" / "crawlers" / "base.py",
    "python_dedup": ROOT / "src" / "needradar" / "services" / "crawl_reliability.py",
    "go_runner": GO_RUNNER,
    "go_service": GO_DIR / "internal" / "collector" / "service.go",
    "go_requester": GO_DIR / "internal" / "collector" / "requester.go",
}


def run_checked(
    command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, env=env, check=True, text=True, capture_output=True)


def command_output(command: list[str], *, cwd: Path = ROOT, fallback: str = "unknown") -> str:
    try:
        return run_checked(command, cwd=cwd).stdout.strip() or fallback
    except (OSError, subprocess.CalledProcessError):
        return fallback


def git_state() -> dict:
    commit = command_output(["git", "rev-parse", "HEAD"])
    status = command_output(["git", "status", "--short"], fallback="")
    return {
        "commit": commit,
        "dirty": bool(status),
        "status_sha256": sha256_bytes(status.encode("utf-8")),
        "status": status.splitlines(),
    }


def cpu_name() -> str:
    for key in ("machdep.cpu.brand_string", "hw.model"):
        value = command_output(["sysctl", "-n", key], fallback="")
        if value:
            return value
    return platform.processor() or "unknown"


def load_snapshot() -> dict:
    output = command_output(["ps", "-axo", "pid=,pcpu=,pmem=,command="], fallback="")
    if not output:
        raise RuntimeError("system load check unavailable")
    rows = []
    suspicious = []
    keywords = ("codepulse", "needradar-rerank", "pytest", "go test", "docker")
    system_markers = (
        "/system/",
        "/usr/libexec/",
        "/usr/sbin/",
        "windowserver",
        "storage.appex",
        "notificationcenter",
        "universalcontrol",
        "loginwindow",
        "/dock.app/",
        "coreaudiod",
        "appleuserhiddrivers",
        "fseventsd",
        "mds",
        "cloudd",
        "fileproviderd",
        "nsurlsessiond",
    )
    for line in output.splitlines():
        parts = line.strip().split(maxsplit=3)
        if len(parts) != 4:
            continue
        try:
            pid, cpu, memory = int(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        command = parts[3]
        lower = command.casefold()
        system_process = any(marker in lower for marker in system_markers)
        row = {
            "pid": pid,
            "cpu_percent": cpu,
            "memory_percent": memory,
            "system_process": system_process,
            "command": command[:240],
        }
        rows.append(row)
        named_benchmark = cpu >= 10 and any(keyword in lower for keyword in keywords)
        generic_user_load = cpu >= 40 and not system_process and pid != os.getpid()
        if named_benchmark or generic_user_load:
            suspicious.append(row)
    rows.sort(key=lambda row: row["cpu_percent"], reverse=True)
    return {
        "known_high_load": bool(suspicious),
        "policy": {
            "named_process_cpu_percent": 10,
            "non_system_process_cpu_percent": 40,
            "system_processes_excluded": True,
        },
        "suspicious": suspicious,
        "top_processes": rows[:10],
    }


def environment() -> dict:
    return {
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu": cpu_name(),
        "logical_cpus": os.cpu_count(),
        "python_version": platform.python_version(),
        "go_version": command_output(["go", "version"], cwd=GO_DIR),
        "gomaxprocs": int(os.environ.get("GOMAXPROCS", os.cpu_count() or 1)),
    }


def build_go_binary() -> None:
    run_checked(["go", "build", "-o", str(GO_BINARY), "./cmd/collector-bench"], cwd=GO_DIR)


def prepare() -> dict:
    state = git_state()
    EVALUATION.mkdir(parents=True, exist_ok=True)
    workload = build_workload(task_count=1000, seed=SEED, items_per_task=10)
    WORKLOAD_PATH.write_text(pretty_json(workload), encoding="utf-8")
    build_go_binary()
    manifest = {
        "schema_version": 2,
        "experiment_id": "needradar-collector-scheduler-v3-20260715",
        "unit": "in-process collection task scheduling",
        "seed": SEED,
        "scenarios": list(SCENARIOS),
        "rules": {
            "fake_io_ms_per_attempt": 5,
            "retry_backoff_ms": 1,
            "max_attempts": 3,
            "retry_injection": "task IDs divisible by 10 return one HTTP 503 before success",
            "duplicate_injection": "last of 10 items repeats item 0 title/content with a distinct URL",
            "fingerprint": "SHA-256 of lowercase normalized title plus content",
            "latency": "shared queue release through terminal task update, including queue wait",
            "throughput": "all submitted tasks divided by internal wall time; failures remain in denominator",
            "resources": "independent process user/system CPU and peak RSS from /usr/bin/time -l",
        },
        "quick": {"task_count": 200, "concurrency": [1, 4, 16], "runs": 1},
        "formal": {
            "task_count": 1000,
            "concurrency": [1, 4, 16, 50],
            "warmup_runs": 3,
            "measurement_runs": 5,
            "order": "fixed-seed shuffled combinations with pairwise language interleaving",
        },
        "startup": {
            "probe": "runner_help_path",
            "measurement_runs": 5,
            "order": "fixed-seed pairwise language interleaving",
            "definition": "independent process runtime startup, runner imports, help parsing/output, and exit",
            "resources": "high-resolution parent wall clock; user/system CPU and peak RSS from /usr/bin/time -l",
        },
        "artifacts": {
            "workload": str(WORKLOAD_PATH.relative_to(ROOT)),
            "workload_sha256": sha256_file(WORKLOAD_PATH),
            "go_binary": str(GO_BINARY),
            "go_binary_sha256": sha256_file(GO_BINARY),
            "sources_sha256": {name: sha256_file(path) for name, path in SOURCE_PATHS.items()},
        },
        "environment": environment(),
        "preparation_load_check": load_snapshot(),
        "runner_git": state,
        "report": {
            "summary": "median of five measured runs with min and max retained",
            "comparison": {
                "throughput": "(Go - Python) / Python",
                "latency": "(Python - Go) / Python",
                "memory": "(Python - Go) / Python",
            },
            "requires_exact_functional_parity": True,
        },
        "limitations": [
            "Deterministic fake I/O does not model public platform latency, quotas, payload variance, or failures.",
            "The comparison excludes SQLite, Vault, LLM, RAG, report generation, and content verification.",
            "The Go service uses in-process state; this benchmark does not establish restart recovery or production SLA.",
            "Results apply only to the frozen local machine, workload, runtime versions, and concurrency matrix.",
            "The machine was not dedicated; macOS system and desktop processes are recorded in load snapshots but excluded from the user-workload refusal rule.",
        ],
    }
    MANIFEST_PATH.write_text(pretty_json(manifest), encoding="utf-8")
    return manifest


def load_manifest(*, require_binary: bool = True) -> tuple[dict, str, dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2:
        raise ValueError("unsupported comparison manifest schema")
    workload = json.loads(WORKLOAD_PATH.read_text(encoding="utf-8"))
    validate_workload(workload)
    artifacts = manifest["artifacts"]
    if sha256_file(WORKLOAD_PATH) != artifacts["workload_sha256"]:
        raise ValueError("workload hash mismatch")
    for name, path in SOURCE_PATHS.items():
        if sha256_file(path) != artifacts["sources_sha256"].get(name):
            raise ValueError(f"source hash mismatch: {name}")
    if require_binary:
        if not GO_BINARY.exists() or sha256_file(GO_BINARY) != artifacts["go_binary_sha256"]:
            raise ValueError("Go benchmark binary is missing or changed")
    return manifest, sha256_file(MANIFEST_PATH), workload


def parse_time_output(stderr: str) -> dict[str, float | int]:
    summary = re.search(r"([0-9.]+)\s+real\s+([0-9.]+)\s+user\s+([0-9.]+)\s+sys", stderr)
    rss = re.search(r"([0-9]+)\s+maximum resident set size", stderr)
    if not summary or not rss:
        raise ValueError(f"could not parse /usr/bin/time -l output: {stderr[-1000:]}")
    return {
        "process_wall_seconds": float(summary.group(1)),
        "user_cpu_seconds": float(summary.group(2)),
        "system_cpu_seconds": float(summary.group(3)),
        "peak_rss_bytes": int(rss.group(1)),
    }


def runner_command(implementation: str, scenario: str, task_count: int, concurrency: int) -> list[str]:
    common = [
        "--workload",
        str(WORKLOAD_PATH),
        "--scenario",
        scenario,
        "--tasks",
        str(task_count),
        "--concurrency",
        str(concurrency),
    ]
    if implementation == "python":
        return [sys.executable, str(PYTHON_RUNNER), *common]
    if implementation == "go":
        return [str(GO_BINARY), *common]
    raise ValueError(f"unsupported implementation: {implementation}")


def execute_runner(implementation: str, scenario: str, task_count: int, concurrency: int) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    process = subprocess.run(
        ["/usr/bin/time", "-l", *runner_command(implementation, scenario, task_count, concurrency)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(f"{implementation} runner failed ({process.returncode}): {process.stderr[-2000:]}")
    result = json.loads(process.stdout)
    result.update(parse_time_output(process.stderr))
    result["startup_overhead_seconds"] = max(0.0, result["process_wall_seconds"] - result["wall_seconds"])
    return result


def startup_command(implementation: str) -> list[str]:
    if implementation == "python":
        return [sys.executable, str(PYTHON_RUNNER), "--help"]
    if implementation == "go":
        return [str(GO_BINARY), "-h"]
    raise ValueError(f"unsupported implementation: {implementation}")


def execute_startup_probe(implementation: str) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    started = time.perf_counter()
    process = subprocess.run(
        ["/usr/bin/time", "-l", *startup_command(implementation)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    wall_seconds = time.perf_counter() - started
    if process.returncode != 0:
        raise RuntimeError(f"{implementation} startup probe failed ({process.returncode}): {process.stderr[-2000:]}")
    return {
        "implementation": implementation,
        "probe": "runner_help_path",
        "wall_seconds": wall_seconds,
        **parse_time_output(process.stderr),
    }


def interleaved_specs(manifest: dict, *, formal: bool) -> list[tuple[str, str, int, str, int]]:
    rng = random.Random(manifest["seed"])
    if formal:
        config = manifest["formal"]
        groups = []
        for scenario in manifest["scenarios"]:
            for concurrency in config["concurrency"]:
                groups.extend((scenario, concurrency, "warmup", index) for index in range(1, config["warmup_runs"] + 1))
                groups.extend(
                    (scenario, concurrency, "measured", index) for index in range(1, config["measurement_runs"] + 1)
                )
    else:
        config = manifest["quick"]
        groups = [
            (scenario, concurrency, "quick", 1)
            for scenario in manifest["scenarios"]
            for concurrency in config["concurrency"]
        ]
    rng.shuffle(groups)
    specs = []
    for scenario, concurrency, phase, iteration in groups:
        order = list(IMPLEMENTATIONS)
        rng.shuffle(order)
        specs.extend((implementation, scenario, concurrency, phase, iteration) for implementation in order)
    return specs


def startup_specs(manifest: dict) -> list[tuple[str, int]]:
    rng = random.Random(manifest["seed"] + 1)
    specs = []
    for iteration in range(1, manifest["startup"]["measurement_runs"] + 1):
        order = list(IMPLEMENTATIONS)
        rng.shuffle(order)
        specs.extend((implementation, iteration) for implementation in order)
    return specs


def run_quick() -> Path:
    manifest, manifest_sha256, workload = load_manifest()
    path = Path("/private/tmp/needradar-collector-comparison-quick.jsonl")
    records = []
    for implementation, scenario, concurrency, phase, iteration in interleaved_specs(manifest, formal=False):
        result = execute_runner(implementation, scenario, manifest["quick"]["task_count"], concurrency)
        validate_result(workload, result, task_count=manifest["quick"]["task_count"])
        result.update(
            {"phase": phase, "iteration": iteration, "manifest_sha256": manifest_sha256, "order": len(records) + 1}
        )
        records.append(result)
    path.write_text("".join(canonical_json(record) + "\n" for record in records), encoding="utf-8")
    return path


def write_report(
    manifest: dict,
    manifest_sha256: str,
    workload: dict,
    records: list[dict],
    startup_records: list[dict],
) -> dict:
    runs_sha256 = sha256_file(RUNS_PATH)
    startup_runs_sha256 = sha256_file(STARTUP_RUNS_PATH)
    report = build_report(
        manifest,
        manifest_sha256,
        workload,
        records,
        runs_sha256,
        startup_records,
        startup_runs_sha256,
    )
    REPORT_JSON_PATH.write_text(pretty_json(report), encoding="utf-8")
    REPORT_MARKDOWN_PATH.write_text(render_report_markdown(report, manifest), encoding="utf-8")
    return report


def run_formal() -> dict:
    manifest, manifest_sha256, workload = load_manifest()
    load = load_snapshot()
    if load["known_high_load"]:
        raise RuntimeError(f"formal benchmark refused due to known high load: {load['suspicious']}")
    if STARTUP_RUNS_PATH.exists() or RUNS_PATH.exists() or REPORT_JSON_PATH.exists() or REPORT_MARKDOWN_PATH.exists():
        raise FileExistsError("formal artifacts already exist; preserve them or move them before a new experiment")
    state = manifest["runner_git"]
    common_metadata = {
        "manifest_sha256": manifest_sha256,
        "workload_sha256": manifest["artifacts"]["workload_sha256"],
        "runner_commit": state["commit"],
        "workspace_dirty": state["dirty"],
        "workspace_status_sha256": state["status_sha256"],
        "environment": manifest["environment"],
        "formal_load_check": load,
    }
    startup_records = []
    for implementation, iteration in startup_specs(manifest):
        result = execute_startup_probe(implementation)
        result.update({"iteration": iteration, "order": len(startup_records) + 1, **common_metadata})
        startup_records.append(result)
        STARTUP_RUNS_PATH.write_text(
            "".join(canonical_json(record) + "\n" for record in startup_records),
            encoding="utf-8",
        )
    validate_startup_records(manifest, manifest_sha256, startup_records)

    records = []
    task_count = manifest["formal"]["task_count"]
    for implementation, scenario, concurrency, phase, iteration in interleaved_specs(manifest, formal=True):
        result = execute_runner(implementation, scenario, task_count, concurrency)
        validate_result(workload, result, task_count=task_count)
        result.update(
            {
                "phase": phase,
                "iteration": iteration,
                "order": len(records) + 1,
                **common_metadata,
            }
        )
        records.append(result)
        RUNS_PATH.write_text("".join(canonical_json(record) + "\n" for record in records), encoding="utf-8")
    validate_records(manifest, manifest_sha256, workload, records)
    return write_report(manifest, manifest_sha256, workload, records, startup_records)


def report_only(*, rewrite: bool = False) -> dict:
    manifest, manifest_sha256, workload = load_manifest(require_binary=False)
    records = load_jsonl(RUNS_PATH)
    startup_records = load_jsonl(STARTUP_RUNS_PATH)
    validate_records(manifest, manifest_sha256, workload, records)
    validate_startup_records(manifest, manifest_sha256, startup_records)
    existing = json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))
    runs_sha256 = sha256_file(RUNS_PATH)
    startup_runs_sha256 = sha256_file(STARTUP_RUNS_PATH)
    validate_report_provenance(existing, manifest_sha256, runs_sha256, startup_runs_sha256)
    rebuilt = build_report(
        manifest,
        manifest_sha256,
        workload,
        records,
        runs_sha256,
        startup_records,
        startup_runs_sha256,
    )
    markdown = render_report_markdown(rebuilt, manifest)
    if not rewrite:
        if pretty_json(rebuilt) != REPORT_JSON_PATH.read_text(encoding="utf-8"):
            raise ValueError("JSON report does not exactly rebuild")
        if markdown != REPORT_MARKDOWN_PATH.read_text(encoding="utf-8"):
            raise ValueError("Markdown report does not exactly rebuild")
    else:
        REPORT_JSON_PATH.write_text(pretty_json(rebuilt), encoding="utf-8")
        REPORT_MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    return rebuilt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare, run, and verify the Python/Go collector comparison")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--quick", action="store_true")
    modes.add_argument("--formal", action="store_true")
    modes.add_argument("--report-only", action="store_true")
    parser.add_argument("--rewrite-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    try:
        if args.prepare:
            result: object = prepare()
        elif args.quick:
            result = {"quick_runs": str(run_quick())}
        elif args.formal:
            result = run_formal()
        else:
            result = report_only(rewrite=args.rewrite_report)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps({"elapsed_seconds": time.monotonic() - started, "result": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
