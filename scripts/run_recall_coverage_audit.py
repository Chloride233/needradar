"""Prepare and report the frozen Rerank Recall Top-20 coverage audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

if __package__:
    from scripts.run_rerank_experiment import (
        ROOT,
        SNAPSHOT_PATH,
        _hash_value,
        _load_completed_labels,
        _read_jsonl,
        _sha256_file,
        _write_jsonl,
        validate_hash_manifest,
        write_hash_manifest,
    )
    from scripts.run_rerank_pilot import (
        ANNOTATION_PATH as PILOT_ANNOTATION_PATH,
    )
    from scripts.run_rerank_pilot import (
        HASHES_PATH as PILOT_HASHES_PATH,
    )
    from scripts.run_rerank_pilot import (
        LABELS_MANIFEST_PATH as PILOT_LABELS_MANIFEST_PATH,
    )
    from scripts.run_rerank_pilot import (
        LABELS_PATH as PILOT_LABELS_PATH,
    )
    from scripts.run_rerank_pilot import (
        POOL_PATH as PILOT_POOL_PATH,
    )
    from scripts.run_rerank_pilot import (
        REPORT_JSON_PATH as PILOT_REPORT_PATH,
    )
else:
    from run_rerank_experiment import (
        ROOT,
        SNAPSHOT_PATH,
        _hash_value,
        _load_completed_labels,
        _read_jsonl,
        _sha256_file,
        _write_jsonl,
        validate_hash_manifest,
        write_hash_manifest,
    )
    from run_rerank_pilot import (
        ANNOTATION_PATH as PILOT_ANNOTATION_PATH,
    )
    from run_rerank_pilot import (
        HASHES_PATH as PILOT_HASHES_PATH,
    )
    from run_rerank_pilot import (
        LABELS_MANIFEST_PATH as PILOT_LABELS_MANIFEST_PATH,
    )
    from run_rerank_pilot import (
        LABELS_PATH as PILOT_LABELS_PATH,
    )
    from run_rerank_pilot import (
        POOL_PATH as PILOT_POOL_PATH,
    )
    from run_rerank_pilot import (
        REPORT_JSON_PATH as PILOT_REPORT_PATH,
    )


AUDIT_DIR = ROOT / "evaluation" / "rerank" / "recall-audit"
MANIFEST_PATH = AUDIT_DIR / "manifest.json"
POOL_PATH = AUDIT_DIR / "pool.jsonl"
ANNOTATION_PATH = AUDIT_DIR / "annotation-template.csv"
LABELS_PATH = AUDIT_DIR / "labels-adjudicated.csv"
LABELS_MANIFEST_PATH = AUDIT_DIR / "labels-adjudicated.manifest.json"
REPORT_JSON_PATH = AUDIT_DIR / "report.json"
REPORT_MD_PATH = AUDIT_DIR / "report.md"
HASHES_PATH = AUDIT_DIR / "artifact-hashes.json"

SCHEMA_VERSION = 1
EXPECTED_QUERY_COUNT = 12
NOISE_DUPLICATE_RATE_THRESHOLD = 0.20
DEDUPLICATION_RULE = "nfkc-casefold-html-unescape-whitespace-v1"
REVIEW_COLUMNS = (
    "query_id",
    "query",
    "split",
    "blind_document_id",
    "platform",
    "title",
    "text_excerpt",
    "relevance_grade",
    "notes",
)


def normalize_content(text: str) -> str:
    """Return the frozen exact-content comparison representation."""
    normalized = unicodedata.normalize("NFKC", html.unescape(text)).casefold()
    return " ".join(normalized.split())


def content_sha256(text: str) -> str:
    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()


def deduplicate_record(record: dict[str, Any], top3_document_ids: set[str]) -> dict[str, Any]:
    """Collapse normalized exact duplicates while retaining their source identities."""
    candidates = sorted(record["candidates"], key=lambda item: (item["original_rank"], item["document_id"]))
    groups: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        groups.setdefault(content_sha256(candidate["text"]), []).append(candidate)

    deduplicated = []
    for digest, group in groups.items():
        representative = group[0]
        document_ids = [item["document_id"] for item in group]
        deduplicated.append(
            {
                **representative,
                "blind_document_id": _hash_value(["recall-top20-audit-v1", record["query_id"], digest])[:16],
                "content_sha256": digest,
                "duplicate_count": len(group),
                "duplicate_document_ids": document_ids,
                "duplicate_original_ranks": [item["original_rank"] for item in group],
                "in_original_top3_union": bool(set(document_ids) & top3_document_ids),
            }
        )
    deduplicated.sort(key=lambda item: (item["original_rank"], item["document_id"]))
    candidate_count = len(candidates)
    duplicate_positions = candidate_count - len(deduplicated)
    duplicate_rate = duplicate_positions / candidate_count if candidate_count else 0.0
    return {
        "query_id": record["query_id"],
        "query": record["query"],
        "split": record["split"],
        "query_metadata": record["query_metadata"],
        "source_candidate_count": candidate_count,
        "deduplicated_candidate_count": len(deduplicated),
        "duplicate_positions": duplicate_positions,
        "duplicate_rate": duplicate_rate,
        "noise_contributor": duplicate_rate >= NOISE_DUPLICATE_RATE_THRESHOLD,
        "original_top3_union_document_ids": sorted(top3_document_ids),
        "candidates": deduplicated,
    }


def build_audit_pool(
    snapshot: list[dict[str, Any]],
    all_zero_query_ids: list[str],
    pilot_pool: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the deterministic 12-query, deduplicated Top-20 review pool."""
    if len(all_zero_query_ids) != EXPECTED_QUERY_COUNT or len(set(all_zero_query_ids)) != EXPECTED_QUERY_COUNT:
        raise ValueError(f"audit requires exactly {EXPECTED_QUERY_COUNT} unique all-zero query IDs")
    snapshot_by_id = {record["query_id"]: record for record in snapshot}
    pilot_by_id = {record["query_id"]: record for record in pilot_pool}
    missing = set(all_zero_query_ids) - set(snapshot_by_id)
    if missing:
        raise ValueError(f"candidate snapshot is missing audit queries: {sorted(missing)}")
    missing_pilot = set(all_zero_query_ids) - set(pilot_by_id)
    if missing_pilot:
        raise ValueError(f"pilot pool is missing audit queries: {sorted(missing_pilot)}")

    result = []
    blind_ids: set[str] = set()
    for query_id in sorted(all_zero_query_ids):
        pilot_record = pilot_by_id[query_id]
        top3_ids = {candidate["document_id"] for candidate in pilot_record["candidates"]}
        record = deduplicate_record(snapshot_by_id[query_id], top3_ids)
        current = {candidate["blind_document_id"] for candidate in record["candidates"]}
        if blind_ids & current:
            raise ValueError("audit blind_document_id collision")
        blind_ids.update(current)
        result.append(record)
    return result


def annotation_bytes(pool: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=REVIEW_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for record in pool:
        for candidate in record["candidates"]:
            metadata = candidate.get("source_metadata", {})
            writer.writerow(
                {
                    "query_id": record["query_id"],
                    "query": record["query"],
                    "split": record["split"],
                    "blind_document_id": candidate["blind_document_id"],
                    "platform": metadata.get("platform", "unknown"),
                    "title": metadata.get("title", ""),
                    "text_excerpt": candidate["text"][:800],
                    "relevance_grade": "",
                    "notes": "",
                }
            )
    return buffer.getvalue().encode("utf-8")


def _validate_source_evidence() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    validate_hash_manifest(PILOT_HASHES_PATH, root=ROOT)
    pilot_report = json.loads(PILOT_REPORT_PATH.read_text(encoding="utf-8"))
    coverage = pilot_report.get("coverage") or {}
    all_zero_query_ids = coverage.get("all_zero_query_ids")
    if not isinstance(all_zero_query_ids, list):
        raise RuntimeError("pilot report does not contain the frozen all-zero query cohort")

    pilot_pool = _read_jsonl(PILOT_POOL_PATH)
    loaded = _load_completed_labels(
        PILOT_LABELS_PATH,
        pilot_pool,
        PILOT_LABELS_MANIFEST_PATH,
        PILOT_ANNOTATION_PATH,
    )
    if loaded is None:
        raise RuntimeError("pilot single-expert labels are incomplete or invalid")
    pilot_labels, pilot_provenance = loaded
    pilot_by_id = {record["query_id"]: record for record in pilot_pool}
    for query_id in all_zero_query_ids:
        if query_id not in pilot_by_id or any(
            pilot_labels[candidate["blind_document_id"]] > 0 for candidate in pilot_by_id[query_id]["candidates"]
        ):
            raise RuntimeError(f"pilot all-zero evidence drifted for query {query_id}")
    return pilot_pool, pilot_report, pilot_provenance


def prepare_audit(output_dir: Path = AUDIT_DIR) -> dict[str, Any]:
    pilot_pool, pilot_report, pilot_provenance = _validate_source_evidence()
    snapshot = _read_jsonl(SNAPSHOT_PATH)
    query_ids = pilot_report["coverage"]["all_zero_query_ids"]
    pool = build_audit_pool(snapshot, query_ids, pilot_pool)

    output_dir.mkdir(parents=True, exist_ok=True)
    pool_path = output_dir / POOL_PATH.name
    annotation_path = output_dir / ANNOTATION_PATH.name
    manifest_path = output_dir / MANIFEST_PATH.name
    hashes_path = output_dir / HASHES_PATH.name
    protected = (pool_path, annotation_path, manifest_path, hashes_path)
    if any(path.exists() for path in protected):
        raise FileExistsError("recall audit package already exists; refusing to overwrite frozen artifacts")

    _write_jsonl(pool_path, pool)
    annotation_path.write_bytes(annotation_bytes(pool))
    source_positions = sum(record["source_candidate_count"] for record in pool)
    unique_candidates = sum(record["deduplicated_candidate_count"] for record in pool)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": "rerank-recall-top20-coverage-audit-v1",
        "scope": {
            "query_count": len(pool),
            "query_ids": [record["query_id"] for record in pool],
            "source_candidate_positions": source_positions,
            "deduplicated_candidates": unique_candidates,
            "duplicate_positions": source_positions - unique_candidates,
        },
        "sources": {
            "candidate_snapshot_path": str(SNAPSHOT_PATH.relative_to(ROOT)),
            "candidate_snapshot_sha256": _sha256_file(SNAPSHOT_PATH),
            "pilot_report_path": str(PILOT_REPORT_PATH.relative_to(ROOT)),
            "pilot_report_sha256": _sha256_file(PILOT_REPORT_PATH),
            "pilot_pool_path": str(PILOT_POOL_PATH.relative_to(ROOT)),
            "pilot_pool_sha256": _sha256_file(PILOT_POOL_PATH),
            "pilot_labels_path": str(PILOT_LABELS_PATH.relative_to(ROOT)),
            "pilot_labels_sha256": _sha256_file(PILOT_LABELS_PATH),
            "pilot_review_method": pilot_provenance["review_method"],
        },
        "deduplication": {
            "rule": DEDUPLICATION_RULE,
            "noise_duplicate_rate_threshold": NOISE_DUPLICATE_RATE_THRESHOLD,
            "representative": "lowest original_rank, then document_id",
        },
        "classification": {
            "rank_failure": "relevant candidate in frozen Top-20 but none in the original judged Top-3 union",
            "coverage_failure": "no relevant candidate in the deduplicated frozen Top-20",
            "corpus_noise_failure": "overlapping contributor when duplicate rate meets the frozen threshold",
            "unresolved": "incomplete labels or conflicting evidence",
        },
        "review": {
            "method": "single_expert_blind_test_retest",
            "rubric": [0, 1, 2],
            "system_blinded": True,
        },
        "artifacts": {
            "pool_path": str(pool_path.relative_to(ROOT)),
            "pool_sha256": _sha256_file(pool_path),
            "annotation_path": str(annotation_path.relative_to(ROOT)),
            "annotation_sha256": _sha256_file(annotation_path),
        },
        "limitations": [
            "Coverage failure means no relevant document in the frozen Top-20, not absence from the full corpus.",
            "Exact normalized duplicate detection does not identify semantic near-duplicates.",
            "This audit does not change retrieval weights, corpus contents, or Rerank model selection.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_hash_manifest([manifest_path, pool_path, annotation_path], hashes_path, root=ROOT)
    return manifest


def classify_query(record: dict[str, Any], labels: dict[str, int]) -> dict[str, Any]:
    grades = {candidate["blind_document_id"]: labels[candidate["blind_document_id"]] for candidate in record["candidates"]}
    relevant = [candidate for candidate in record["candidates"] if grades[candidate["blind_document_id"]] > 0]
    original_top3_relevant = [candidate for candidate in relevant if candidate["in_original_top3_union"]]
    if original_top3_relevant:
        category = "unresolved"
        reason = "The audit reviewer marked an original Top-3 union candidate relevant, conflicting with frozen pilot labels."
    elif relevant:
        category = "rank_failure"
        reason = "At least one relevant candidate exists below the original judged Top-3 union in the frozen Top-20."
    else:
        category = "coverage_failure"
        reason = "No relevant candidate was found in the deduplicated frozen Top-20."
    return {
        "query_id": record["query_id"],
        "category": category,
        "reason": reason,
        "noise_contributor": record["noise_contributor"],
        "source_candidate_count": record["source_candidate_count"],
        "deduplicated_candidate_count": record["deduplicated_candidate_count"],
        "duplicate_positions": record["duplicate_positions"],
        "duplicate_rate": record["duplicate_rate"],
        "grade_counts": {str(grade): sum(value == grade for value in grades.values()) for grade in (0, 1, 2)},
        "relevant_blind_document_ids": [candidate["blind_document_id"] for candidate in relevant],
    }


def build_report(pool: list[dict[str, Any]], labels: dict[str, int], provenance: dict[str, Any]) -> dict[str, Any]:
    expected = {candidate["blind_document_id"] for record in pool for candidate in record["candidates"]}
    if set(labels) != expected:
        raise ValueError("audit labels do not exactly cover the frozen review pool")
    queries = [classify_query(record, labels) for record in pool]
    category_counts = Counter(record["category"] for record in queries)
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": "rerank-recall-top20-coverage-audit-v1",
        "label_status": "single_expert_test_retest_validated",
        "label_provenance": provenance,
        "summary": {
            "query_count": len(queries),
            "classification_counts": dict(sorted(category_counts.items())),
            "noise_contributor_queries": sum(record["noise_contributor"] for record in queries),
            "source_candidate_positions": sum(record["source_candidate_count"] for record in queries),
            "deduplicated_candidates": sum(record["deduplicated_candidate_count"] for record in queries),
            "duplicate_positions": sum(record["duplicate_positions"] for record in queries),
        },
        "queries": queries,
        "limitations": [
            "Coverage failure means no relevant document in the frozen Top-20, not absence from the full corpus.",
            "Noise contribution uses normalized exact duplicates and does not measure semantic near-duplicates.",
            "The audit explains candidate coverage and does not select a Reranker model.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Rerank Recall Top-20 coverage audit",
        "",
        f"- Queries: {summary['query_count']}",
        f"- Source candidate positions: {summary['source_candidate_positions']}",
        f"- Deduplicated candidates: {summary['deduplicated_candidates']}",
        f"- Duplicate positions: {summary['duplicate_positions']}",
        f"- Noise contributors: {summary['noise_contributor_queries']}",
        "",
        "## Classification",
        "",
        "| Category | Queries |",
        "| --- | ---: |",
    ]
    for category in ("rank_failure", "coverage_failure", "unresolved"):
        lines.append(f"| `{category}` | {summary['classification_counts'].get(category, 0)} |")
    lines.extend(
        [
            "",
            "## Per-query evidence",
            "",
            "| Query ID | Category | Unique / Top-20 | Duplicate rate | Noise contributor |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for record in report["queries"]:
        lines.append(
            f"| `{record['query_id']}` | `{record['category']}` | "
            f"{record['deduplicated_candidate_count']}/{record['source_candidate_count']} | "
            f"{record['duplicate_rate']:.1%} | {'yes' if record['noise_contributor'] else 'no'} |"
        )
    lines.extend(["", "## Limitations", "", *[f"- {item}" for item in report["limitations"]]])
    return "\n".join(lines) + "\n"


def rebuild_report(output_dir: Path = AUDIT_DIR) -> dict[str, Any]:
    manifest_path = output_dir / MANIFEST_PATH.name
    pool_path = output_dir / POOL_PATH.name
    annotation_path = output_dir / ANNOTATION_PATH.name
    labels_path = output_dir / LABELS_PATH.name
    labels_manifest_path = output_dir / LABELS_MANIFEST_PATH.name
    report_json_path = output_dir / REPORT_JSON_PATH.name
    report_md_path = output_dir / REPORT_MD_PATH.name
    hashes_path = output_dir / HASHES_PATH.name

    validate_hash_manifest(hashes_path, root=ROOT)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pool = _read_jsonl(pool_path)
    loaded = _load_completed_labels(labels_path, pool, labels_manifest_path, annotation_path)
    if loaded is None:
        raise RuntimeError("recall audit single-expert labels are incomplete or invalid")
    labels, provenance = loaded
    report = build_report(pool, labels, provenance)
    report["manifest_sha256"] = _sha256_file(manifest_path)
    report["pool_sha256"] = manifest["artifacts"]["pool_sha256"]
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_md_path.write_text(render_markdown(report), encoding="utf-8")

    label_manifest = json.loads(labels_manifest_path.read_text(encoding="utf-8"))
    first_path = output_dir / str(label_manifest["first_pass_path"])
    retest_path = output_dir / str(label_manifest["retest_path"])
    write_hash_manifest(
        [
            manifest_path,
            pool_path,
            annotation_path,
            labels_path,
            labels_manifest_path,
            first_path,
            retest_path,
            report_json_path,
            report_md_path,
        ],
        hashes_path,
        root=ROOT,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--prepare", action="store_true")
    actions.add_argument("--rebuild-report", action="store_true")
    args = parser.parse_args()
    result = prepare_audit() if args.prepare else rebuild_report()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
