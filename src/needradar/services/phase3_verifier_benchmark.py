from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

PLATFORMS = ("github", "stackoverflow", "juejin")
LENGTH_BUCKETS = ("short", "medium", "long")
VALID_VERDICTS = {"supported", "partially", "unverifiable", "contradicted", "hallucination"}
FILLER = (
    "This background passage describes how the review separates direct source evidence from interpretation. "
    "It intentionally avoids adding measurements, named entities, or new factual conclusions. "
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _jsonl_text(records: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)


def _canonical_sha256(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).casefold()
            if "author" in normalized or normalized in {"claims", "annotation_status"}:
                return True
            if _contains_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def claim_id(quote: str, section: str, start: int) -> str:
    normalized = " ".join(quote.split()).casefold()
    payload = f"{normalized}\n{section.strip()}\n{start}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _clean_text(value: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip().replace('"', "'")
    return cleaned[:limit].rstrip()


def _filler_to_length(body: str, minimum: int) -> str:
    parts = [body]
    while sum(len(part) for part in parts) < minimum:
        parts.append("\n\n" + FILLER)
    return "".join(parts)


def _claim(
    body: str,
    quote: str,
    section: str,
    verdict: str,
    source_ids: list[str],
    *,
    needs_correction: bool = False,
) -> dict[str, Any]:
    start = body.index(quote)
    return {
        "claim_id": claim_id(quote, section, start),
        "quote": quote,
        "section": section,
        "start": start,
        "end": start + len(quote),
        "verdict": verdict,
        "source_ids": source_ids,
        "needs_correction": needs_correction,
    }


def _variant(index: int, flagged: bool) -> tuple[str, str, bool]:
    if flagged:
        return (
            (
                ("unsupported_number", "hallucination", False),
                ("wrong_attribution", "contradicted", False),
                ("categorical_contradiction", "contradicted", True),
            )
        )[index % 3]
    return (
        (
            ("supported_control", "supported", False),
            ("exaggerated_scope", "partially", False),
            ("missing_evidence", "unverifiable", False),
        )
    )[index % 3]


def _variant_quote(variant: str, platform: str, first_title: str, second_title: str) -> str:
    wrong_platform = {"github": "Juejin", "stackoverflow": "GitHub", "juejin": "Stack Overflow"}[platform]
    variants = {
        "supported_control": f'The reviewed sources are titled "{first_title}" and "{second_title}".',
        "exaggerated_scope": "The evidence suggests the same concern affects every software team without exception.",
        "missing_evidence": "An independent deployment reduced operating cost during the previous quarter.",
        "unsupported_number": "Exactly 97% of affected users abandoned the tool within one week.",
        "wrong_attribution": f'The source titled "{first_title}" was published as a {wrong_platform} item.',
        "categorical_contradiction": "The report shows both that the tooling concern never occurs and that it occurs in the reviewed sources.",
    }
    return variants[variant]


def _build_bundle(
    platform: str,
    index: int,
    ordinal: int,
    source_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    stratum = "controlled" if index < 6 else "naturalistic"
    flagged = index % 2 == 1
    length_bucket = LENGTH_BUCKETS[ordinal % len(LENGTH_BUCKETS)]
    variant, variant_verdict, contradiction = _variant(index, flagged)
    first, second = source_records
    first_title = _clean_text(first["title"], 100)
    second_title = _clean_text(second["title"], 100)
    detail = _clean_text(first["content"], 150)
    quote_one = f'The first source is titled "{first_title}".'
    quote_two = f'The source states: "{detail}".'
    quote_three = _variant_quote(variant, platform, first_title, second_title)

    if stratum == "controlled":
        opening = f"## 核心发现\n\n1. **{quote_one}**\n\n"
        second_line = f"2. **{quote_two}**\n\n"
        variant_line = f"3. **{quote_three}**"
    else:
        opening = f"## 核心发现\n\nThe evidence review begins with a direct observation. {quote_one}\n\n"
        second_line = f"A separate passage preserves the wording needed for verification. {quote_two}\n\n"
        variant_line = f"## 用户痛点深度分析\n\nThe review also records this conclusion. {quote_three}"

    body = opening
    if length_bucket == "long":
        body = _filler_to_length(body, 8100)
        body += "\n\n" + second_line + variant_line
    else:
        body += second_line + variant_line
        if length_bucket == "medium":
            body = _filler_to_length(body, 4800)
    body += "\n\n## 机会与建议\n\nFurther review should preserve direct citations and distinguish evidence from interpretation.\n"

    bundle_id = hashlib.sha256(f"{platform}:{index}:{first['id']}:{second['id']}".encode()).hexdigest()[:16]
    sources = [
        {
            "id": source["id"],
            "platform": source["platform"],
            "source_url": source["source_url"],
            "title": source["title"],
            "content": source["content"][:800],
        }
        for source in source_records
    ]
    input_record = {
        "id": bundle_id,
        "platform": platform,
        "stratum": stratum,
        "length_bucket": length_bucket,
        "report_title": f"Verifier benchmark {platform} {index + 1}",
        "report_meta": {"source_ids": [source["id"] for source in sources]},
        "report_body": body,
        "sources": sources,
    }
    gold_record = {
        "id": bundle_id,
        "platform": platform,
        "stratum": stratum,
        "length_bucket": length_bucket,
        "flagged": flagged,
        "mutation_type": variant,
        "internal_contradiction": contradiction,
        "annotation_status": "complete" if stratum == "controlled" else "pending_independent_review",
        "annotation_method": "constructed" if stratum == "controlled" else "draft_by_construction",
        "claims": [
            _claim(body, quote_one, "核心发现", "supported", [first["id"]]),
            _claim(body, quote_two, "核心发现", "supported", [first["id"]]),
            _claim(
                body,
                quote_three,
                "核心发现" if stratum == "controlled" else "用户痛点深度分析",
                variant_verdict,
                [source["id"] for source in sources],
                needs_correction=variant_verdict in {"partially", "contradicted", "hallucination"},
            ),
        ],
    }
    return input_record, gold_record


def build_verifier_benchmark(corpus_path: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    corpus = _read_jsonl(corpus_path)
    by_platform = {
        platform: sorted((record for record in corpus if record["platform"] == platform), key=lambda item: item["id"])
        for platform in PLATFORMS
    }
    for platform, records in by_platform.items():
        if len(records) < 20:
            raise ValueError(f"{platform} requires at least 20 frozen source records")

    inputs = []
    gold = []
    ordinal = 0
    for platform in PLATFORMS:
        for index in range(10):
            input_record, gold_record = _build_bundle(
                platform,
                index,
                ordinal,
                by_platform[platform][index * 2 : index * 2 + 2],
            )
            inputs.append(input_record)
            gold.append(gold_record)
            ordinal += 1

    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / "verifier-benchmark.jsonl"
    gold_path = output_dir / "verifier-gold.jsonl"
    manifest_path = output_dir / "verifier-benchmark-manifest.json"
    input_text = _jsonl_text(inputs)
    gold_text = _jsonl_text(gold)
    input_path.write_text(input_text, encoding="utf-8")
    gold_path.write_text(gold_text, encoding="utf-8")
    pending = sum(record["annotation_status"] != "complete" for record in gold)
    manifest = {
        "schema_version": 1,
        "source_corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "input_records": len(inputs),
        "gold_records": len(gold),
        "platform_counts": dict(sorted(Counter(record["platform"] for record in inputs).items())),
        "stratum_counts": dict(sorted(Counter(record["stratum"] for record in inputs).items())),
        "length_counts": dict(sorted(Counter(record["length_bucket"] for record in inputs).items())),
        "clean_reports": sum(not record["flagged"] for record in gold),
        "flagged_reports": sum(record["flagged"] for record in gold),
        "pending_annotations": pending,
        "complete": pending == 0,
        "author_fields_stored": False,
        "gold_fields_in_inputs": False,
        "input_sha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        "input_canonical_sha256": _canonical_sha256(inputs),
        "gold_sha256": hashlib.sha256(gold_text.encode("utf-8")).hexdigest(),
        "gold_canonical_sha256": _canonical_sha256(gold),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_verifier_benchmark(input_path, gold_path, manifest_path, require_complete=False)
    return input_path, gold_path, manifest_path


def apply_naturalistic_adjudication(
    input_path: Path,
    gold_path: Path,
    manifest_path: Path,
    adjudication_path: Path,
) -> dict[str, Any]:
    gold = _read_jsonl(gold_path)
    decisions = {record["id"]: record for record in _read_jsonl(adjudication_path)}
    pending_ids = {record["id"] for record in gold if record["annotation_status"] != "complete"}
    if set(decisions) != pending_ids:
        raise ValueError("naturalistic adjudication IDs do not match pending gold IDs")
    for record in gold:
        if record["id"] not in decisions:
            continue
        decision = decisions[record["id"]]
        verdicts = decision.get("verdicts", [])
        if len(verdicts) != len(record["claims"]) or any(verdict not in VALID_VERDICTS for verdict in verdicts):
            raise ValueError(f"invalid adjudicated verdicts for {record['id']}")
        for claim, verdict in zip(record["claims"], verdicts):
            claim["verdict"] = verdict
            claim["needs_correction"] = verdict in {"partially", "contradicted", "hallucination"}
        record["internal_contradiction"] = bool(decision["internal_contradiction"])
        record["annotation_status"] = "complete"
        record["annotation_method"] = "dual_agent_blind_with_root_adjudication"
        record["adjudication_notes"] = decision.get("notes", "")

    gold_text = _jsonl_text(gold)
    gold_path.write_text(gold_text, encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "pending_annotations": 0,
            "complete": True,
            "gold_sha256": hashlib.sha256(gold_text.encode("utf-8")).hexdigest(),
            "gold_canonical_sha256": _canonical_sha256(gold),
            "adjudication_sha256": hashlib.sha256(adjudication_path.read_bytes()).hexdigest(),
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validate_verifier_benchmark(input_path, gold_path, manifest_path, require_complete=True)


def validate_verifier_benchmark(
    input_path: Path,
    gold_path: Path,
    manifest_path: Path,
    *,
    require_complete: bool,
) -> dict[str, Any]:
    inputs = _read_jsonl(input_path)
    gold = _read_jsonl(gold_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    input_ids = [record["id"] for record in inputs]
    gold_by_id = {record["id"]: record for record in gold}
    if len(inputs) != len(gold) or len(input_ids) != len(set(input_ids)) or set(input_ids) != set(gold_by_id):
        raise ValueError("verifier benchmark input and gold IDs do not match exactly")
    if len(inputs) != 30:
        raise ValueError("verifier benchmark must contain exactly 30 bundles")
    if Counter(record["platform"] for record in inputs) != Counter({platform: 10 for platform in PLATFORMS}):
        raise ValueError("verifier benchmark platform quotas do not match")
    if Counter(record["stratum"] for record in inputs) != Counter({"controlled": 18, "naturalistic": 12}):
        raise ValueError("verifier benchmark stratum quotas do not match")
    if Counter(record["length_bucket"] for record in inputs) != Counter({bucket: 10 for bucket in LENGTH_BUCKETS}):
        raise ValueError("verifier benchmark length quotas do not match")
    if sum(gold_by_id[record_id]["flagged"] for record_id in input_ids) != 15:
        raise ValueError("verifier benchmark must contain 15 flagged reports")
    for record in inputs:
        if _contains_forbidden_key(record):
            raise ValueError("verifier benchmark inputs contain author or gold fields")
        body = record["report_body"]
        for claim in gold_by_id[record["id"]]["claims"]:
            if body[claim["start"] : claim["end"]] != claim["quote"]:
                raise ValueError(f"claim offsets do not match for {claim['claim_id']}")
            if claim["claim_id"] != claim_id(claim["quote"], claim["section"], claim["start"]):
                raise ValueError(f"claim ID does not match for {claim['claim_id']}")
    input_text = input_path.read_text(encoding="utf-8")
    gold_text = gold_path.read_text(encoding="utf-8")
    expected_hashes = {
        "input_sha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        "input_canonical_sha256": _canonical_sha256(inputs),
        "gold_sha256": hashlib.sha256(gold_text.encode("utf-8")).hexdigest(),
        "gold_canonical_sha256": _canonical_sha256(gold),
    }
    if any(manifest.get(key) != value for key, value in expected_hashes.items()):
        raise ValueError("verifier benchmark manifest hashes do not match")
    pending = sum(record["annotation_status"] != "complete" for record in gold)
    if manifest.get("pending_annotations") != pending or manifest.get("complete") != (pending == 0):
        raise ValueError("verifier benchmark annotation status does not match manifest")
    if require_complete and pending:
        raise ValueError(f"verifier benchmark has {pending} pending independent annotations")
    return manifest
