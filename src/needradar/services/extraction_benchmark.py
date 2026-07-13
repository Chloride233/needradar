from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from needradar.schemas.schemas import ExtractedRequirement, RawDiscussionItem
from needradar.services.noise_filter import _rule_filter


def _load_extraction_prompt(root: Path) -> str:
    prompts = yaml.safe_load((root / "config" / "prompts.yaml").read_text(encoding="utf-8"))
    return prompts["requirement_extraction"]


async def run_extraction_benchmark(
    dataset_path: Path,
    output_path: Path,
    root: Path,
    provider: Any,
    limit: int | None = None,
) -> dict[str, Any]:
    records = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    if limit is not None:
        records = records[:limit]
    completed = {}
    if output_path.exists():
        completed = {
            record["id"]: record
            for line in output_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for record in [json.loads(line)]
        }
    prompt = _load_extraction_prompt(root)
    predictions = dict(completed)
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_cny": 0.0}

    for record in records:
        if record["id"] in completed:
            continue
        item = RawDiscussionItem(
            platform=record["platform"],
            source_url=record["source_url"],
            title=record["title"],
            content=record["content"],
            tags=record.get("tags", []),
        )
        rejected = _rule_filter(item)
        if rejected is not None:
            prediction = {
                "id": record["id"],
                "requirement_present": "no",
                "title": "",
                "description": "",
                "pain_point": "",
                "use_case": "",
                "sentiment": "mild",
                "emotion": "neutral",
                "confidence": rejected.confidence,
                "rejection_reason": rejected.reason,
            }
        else:
            text = f"讨论标题：{item.title}\n\n讨论内容：\n{item.content}"
            extracted = None
            extraction_error = ""
            for _attempt in range(2):
                try:
                    extracted = await provider.extract_structured(
                        prompt=prompt,
                        text=text,
                        schema=ExtractedRequirement,
                    )
                    extraction_error = ""
                    break
                except (ValueError, ConnectionError, TimeoutError, RuntimeError) as error:
                    extraction_error = str(error)
                finally:
                    call_usage = provider.pop_last_usage() or {}
                    for key in usage:
                        usage[key] += call_usage.get(key, 0)
            if extracted is None:
                prediction = {
                    "id": record["id"],
                    "requirement_present": "error",
                    "title": "",
                    "description": "",
                    "pain_point": "",
                    "use_case": "",
                    "sentiment": "mild",
                    "emotion": "neutral",
                    "confidence": 0.0,
                    "rejection_reason": "",
                    "extraction_error": extraction_error[:500],
                }
            else:
                prediction = {
                    "id": record["id"],
                    "requirement_present": "yes",
                    "title": extracted.title,
                    "description": extracted.description,
                    "pain_point": extracted.pain_point,
                    "use_case": extracted.use_case,
                    "sentiment": extracted.sentiment.value,
                    "emotion": extracted.emotion.value,
                    "confidence": extracted.confidence,
                    "rejection_reason": "",
                    "extraction_error": "",
                }
        predictions[record["id"]] = prediction
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(
                json.dumps(predictions[item["id"]], ensure_ascii=False) + "\n"
                for item in records
                if item["id"] in predictions
            ),
            encoding="utf-8",
        )

    return {
        "requested": len(records),
        "completed": sum(record["id"] in predictions for record in records),
        "resumed": len(completed),
        "usage_this_run": usage,
        "rag_enabled": False,
        "extraction_failures": sum(
            predictions[record["id"]]["requirement_present"] == "error"
            for record in records
            if record["id"] in predictions
        ),
    }
