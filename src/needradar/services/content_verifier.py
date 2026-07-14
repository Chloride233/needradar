from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from loguru import logger

from needradar.llm.provider import llm
from needradar.services.vault_store import vault

# ── Data structures ──


@dataclass
class Claim:
    text: str
    section: str = ""
    quote: str = ""
    start: int | None = None
    end: int | None = None
    claim_id: str = ""
    verdict: str = "unverifiable"  # supported / partially / unverifiable / contradicted / hallucination
    confidence: float = 0.0  # 0-1
    evidence: str = ""
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class VerificationOutput:
    overall_score: float = 0.0  # 0-100
    fact_check_score: float = 0.0
    consistency_score: float = 0.0
    source_reliability_score: float = 0.0
    claims: list[Claim] = field(default_factory=list)
    suggestions: list[dict[str, str]] = field(default_factory=list)
    hallucination_count: int = 0
    flagged_count: int = 0


class VerificationStageError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        super().__init__(f"{stage}: {message}")


# ── Platform reliability weights ──

PLATFORM_RELIABILITY = {
    "github": 0.85,
    "stackoverflow": 0.80,
    "juejin": 0.70,
    "unknown": 0.40,
}
VALID_VERDICTS = {"supported", "partially", "unverifiable", "contradicted", "hallucination"}


# ── Core verifier ──


class ContentVerifier:
    """Multi-dimensional hallucination detection and content verification."""

    def __init__(self, provider=None, *, strict: bool = False) -> None:
        self._injected_provider = provider
        self._strict = strict
        self._usage_records: list[dict] = []
        self._provider_attempts = 0
        self._call_traces: list[dict] = []

    @property
    def _provider(self):
        return self._injected_provider or llm

    async def _complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        self._provider_attempts += 1
        if self._strict:
            kwargs["fallback_to_default"] = False
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        trace = {
            "prompt_sha256": self._text_sha256(
                "\n".join(message["content"] for message in messages if message.get("role") == "system")
            ),
            "input_sha256": self._text_sha256(
                "\n".join(message["content"] for message in messages if message.get("role") != "system")
            ),
            "parameters_sha256": self._text_sha256(json.dumps(kwargs, sort_keys=True, default=str)),
        }
        try:
            response = await self._provider.complete(messages, **kwargs)
        except Exception as error:
            self._call_traces.append({**trace, "status": "failed", "error_type": type(error).__name__})
            raise
        self._call_traces.append({**trace, "status": "success", "output_sha256": self._text_sha256(response)})
        return response

    def pop_provider_attempts(self) -> int:
        attempts = self._provider_attempts
        self._provider_attempts = 0
        return attempts

    def pop_call_traces(self) -> list[dict]:
        traces = self._call_traces
        self._call_traces = []
        return traces

    @staticmethod
    def _text_sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _pop_usage(self) -> None:
        pop_last_usage = getattr(self._provider, "pop_last_usage", None)
        u = pop_last_usage() if pop_last_usage else None
        if u:
            self._usage_records.append(u)

    @staticmethod
    def _claim_id(quote: str, section: str, start: int) -> str:
        normalized = " ".join(quote.split()).casefold()
        payload = f"{normalized}\n{section.strip()}\n{start}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    async def verify_report(self, report_title: str) -> VerificationOutput:
        self._usage_records = []

        # 1. Load report and source data
        path = vault.find_by_title("初稿", report_title)
        if not path:
            logger.warning("verify_report_not_found", title=report_title)
            if self._strict:
                raise VerificationStageError("input_loading", f"report not found: {report_title}")
            return VerificationOutput()
        meta, body = vault.read(path)
        # 2. Extract claims from report body
        claims = await self._extract_claims(body)
        self._pop_usage()

        # 3. Collect source evidence
        source_docs = self._collect_sources(meta)

        # 4. Fact-check each claim against sources
        claims = await self._fact_check_claims(claims, source_docs)
        self._pop_usage()

        # 5. Logical consistency check across claims
        consistency_score = await self._check_consistency(body, claims)
        self._pop_usage()

        # 6. Source reliability assessment
        source_reliability = self._assess_source_reliability(source_docs, meta)

        # 7. Aggregate scores
        output = self._aggregate(claims, consistency_score, source_reliability)

        # 8. Generate correction suggestions
        output.suggestions = self._generate_suggestions(output.claims)

        logger.info(
            "verification_complete",
            report=report_title,
            overall=output.overall_score,
            hallucinations=output.hallucination_count,
            flagged=output.flagged_count,
        )
        return output

    # ── Step 2: Claim Extraction ──

    async def _extract_claims(self, body: str) -> list[Claim]:
        """Use LLM to extract verifiable factual claims from the report."""
        # Batch all sections into one call to reduce API calls and improve cache hits
        all_claims = await self._llm_extract_claims_batch(body)

        # Also extract from bold/highlighted statements (rule-based)
        all_claims.extend(self._rule_based_claims(body))

        # Deduplicate by text similarity
        return self._deduplicate_claims(all_claims)

    async def _llm_extract_claims_batch(self, body: str) -> list[Claim]:
        """Extract claims from entire report body in a single call."""
        if len(body.strip()) < 50:
            return []
        if self._strict:
            output_instruction = (
                '以JSON数组返回，格式：[{"quote": "报告中的完整原文声明", "section": "所在章节名"}]。'
                "quote必须逐字复制报告中的连续文本，不要返回字符偏移。\n"
                "最多提取12条。无声明返回 []。"
            )
        else:
            output_instruction = (
                '以JSON数组返回，格式：[{"text": "声明", "section": "所在章节名"}]\n最多提取20条。无声明返回 []。'
            )
        try:
            resp = await self._complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是事实核查专家。从报告中提取所有可验证的事实性声明。\n"
                            "每条声明应是一个可以用真/假/部分真来验证的具体论断。\n"
                            "忽略主观观点和推荐建议，只提取事实性内容。\n\n" + output_instruction
                        ),
                    },
                    {"role": "user", "content": body[:4000]},
                ],
                temperature=0.1,
                max_tokens=2000,
            )
            raw = resp.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```\w*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            items = json.loads(raw)
            if not isinstance(items, list):
                if self._strict:
                    raise VerificationStageError("claim_extraction", "response is not a JSON list")
                items = []
            if self._strict:
                if len(items) > 12:
                    raise VerificationStageError("claim_extraction", "response contains at most 12 claims")
                claims = []
                for item in items:
                    if not isinstance(item, dict):
                        raise VerificationStageError("claim_extraction", "claim is not an object")
                    quote = item.get("quote")
                    section = item.get("section", "")
                    if not isinstance(quote, str) or len(quote) <= 5:
                        raise VerificationStageError("claim_extraction", "claim quote is missing or too short")
                    start = body.find(quote)
                    if start < 0:
                        raise VerificationStageError("claim_extraction", "claim quote does not occur in report")
                    end = start + len(quote)
                    claims.append(
                        Claim(
                            text=quote,
                            section=str(section),
                            quote=quote,
                            start=start,
                            end=end,
                            claim_id=self._claim_id(quote, str(section), start),
                        )
                    )
                return claims
            return [
                Claim(
                    text=item["text"],
                    section=item.get("section", ""),
                )
                for item in items
                if isinstance(item, dict) and "text" in item and len(item["text"]) > 5
            ]
        except Exception as e:
            if self._strict:
                if isinstance(e, VerificationStageError):
                    raise
                raise VerificationStageError("claim_extraction", str(e)) from e
            logger.warning("claim_extraction_failed", error=str(e))
            return []

    def _rule_based_claims(self, body: str) -> list[Claim]:
        """Extract claims from bold/highlighted text patterns."""
        claims = []
        seen = set()
        # Bold text in numbered items: 1. **claim text**
        for m in re.finditer(r"\d+\.\s*\*\*(.{10,150}?)\*\*", body):
            text = m.group(1).strip().rstrip("：:")
            if text not in seen:
                seen.add(text)
                start = body.find(text, m.start(1), m.end(1))
                claims.append(
                    Claim(
                        text=text,
                        section="核心发现",
                        quote=text,
                        start=start,
                        end=start + len(text),
                        claim_id=self._claim_id(text, "核心发现", start),
                    )
                )
        return claims

    def _deduplicate_claims(self, claims: list[Claim]) -> list[Claim]:
        seen_texts: list[str] = []
        unique: list[Claim] = []
        for c in claims:
            # Simple dedup: skip if >80% overlap with existing
            is_dup = False
            for s in seen_texts:
                if self._text_overlap(c.text, s) > 0.8:
                    is_dup = True
                    break
            if not is_dup:
                seen_texts.append(c.text)
                unique.append(c)
        return unique

    @staticmethod
    def _text_overlap(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    # ── Step 3: Source Collection ──

    def _collect_sources(self, report_meta: dict) -> list[dict]:
        """Gather source requirement data referenced by this report."""
        refs = report_meta.get("关联需求", [])
        sources = []
        for ref in refs:
            # Extract title from [[path|title]] format
            m = re.search(r"\[\[.*?/(.*?)\|", ref)
            if m:
                title = m.group(1).strip()
            else:
                title = ref.strip("[]|")
            src = vault.find_by_title("需求", title)
            if src:
                meta, body = vault.read(src)
                sources.append(
                    {
                        "title": meta.get("标题", title),
                        "platform": meta.get("来源平台", "unknown"),
                        "sentiment": meta.get("情感倾向", "moderate"),
                        "content": (body or meta.get("_body", ""))[:800],
                    }
                )
        return sources

    # ── Step 4: Fact-Checking ──

    async def _fact_check_claims(
        self,
        claims: list[Claim],
        sources: list[dict],
        *,
        source_chars: int = 200,
        include_content: bool = True,
    ) -> list[Claim]:
        """Verify all claims against source evidence in one call for max cache reuse."""
        if not claims:
            return claims
        if not sources:
            for c in claims:
                c.verdict = "unverifiable"
                c.confidence = 0.3
                c.risk_flags.append("无来源数据可供交叉验证")
            return claims

        source_summary = "\n".join(
            f"[{source['platform']}] {source['title']}"
            + (f": {source['content'][:source_chars]}" if include_content else "")
            for source in sources[:15]
        )

        # Send all claims in one call — shared source_summary prefix gets cached
        # Split into batches of 12 if too many claims
        for i in range(0, len(claims), 12):
            batch = claims[i : i + 12]
            await self._llm_fact_check_batch(batch, source_summary)

        return claims

    async def _llm_fact_check_batch(self, claims: list[Claim], source_summary: str) -> None:
        claim_list = "\n".join(f"{i + 1}. {c.text}" for i, c in enumerate(claims))
        try:
            resp = await self._complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是事实核查验证引擎。根据提供的来源数据，逐一验证以下声明的准确性。\n\n"
                            "对每条声明返回JSON：\n"
                            '[{"idx": 1, "verdict": "supported|partially|unverifiable|contradicted|hallucination", '
                            '"confidence": 0.0-1.0, "evidence": "支持/反驳的依据简述", '
                            '"flags": ["风险标记列表"]}]\n\n'
                            "判定标准：\n"
                            "- supported: 来源数据明确支持该声明\n"
                            "- partially: 部分支持但有关键细节偏差\n"
                            "- unverifiable: 来源中无相关信息\n"
                            "- contradicted: 来源数据与声明矛盾\n"
                            "- hallucination: 声明包含虚构的具体数据(如百分比、数量等)且与来源不符"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"来源数据：\n{source_summary}\n\n待验证声明：\n{claim_list}",
                    },
                ],
                temperature=0.05,
                max_tokens=2000,
            )

            raw = resp.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```\w*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            results = json.loads(raw)
            if not isinstance(results, list):
                if self._strict:
                    raise VerificationStageError("fact_check", "response is not a JSON list")
                return

            if self._strict:
                indexed_results = {}
                for result in results:
                    if not isinstance(result, dict):
                        raise VerificationStageError("fact_check", "result is not an object")
                    idx = result.get("idx")
                    if not isinstance(idx, int) or idx < 1 or idx > len(claims):
                        raise VerificationStageError("fact_check", "result index is out of range")
                    if idx in indexed_results:
                        raise VerificationStageError("fact_check", f"duplicate result index: {idx}")
                    if result.get("verdict") not in VALID_VERDICTS:
                        raise VerificationStageError("fact_check", f"invalid verdict at index {idx}")
                    if not isinstance(result.get("confidence"), (int, float)):
                        raise VerificationStageError("fact_check", f"invalid confidence at index {idx}")
                    if not isinstance(result.get("flags", []), list):
                        raise VerificationStageError("fact_check", f"invalid flags at index {idx}")
                    indexed_results[idx] = result
                expected_indices = set(range(1, len(claims) + 1))
                if set(indexed_results) != expected_indices:
                    raise VerificationStageError("fact_check", "response is missing one or more claim indices")
                results = [indexed_results[idx] for idx in sorted(indexed_results)]

            for r in results:
                idx = r.get("idx", 0) - 1
                if 0 <= idx < len(claims):
                    claims[idx].verdict = r.get("verdict", "unverifiable")
                    claims[idx].confidence = min(1.0, max(0.0, float(r.get("confidence", 0.5))))
                    claims[idx].evidence = r.get("evidence", "")
                    claims[idx].risk_flags = r.get("flags", [])
        except Exception as e:
            if self._strict:
                if isinstance(e, VerificationStageError):
                    raise
                raise VerificationStageError("fact_check", str(e)) from e
            logger.warning("fact_check_failed", error=str(e))
            for c in claims:
                c.verdict = "unverifiable"
                c.confidence = 0.3

    # ── Step 5: Consistency Check ──

    async def _check_consistency(self, body: str, claims: list[Claim]) -> float:
        """Check for logical contradictions within the report."""
        # Rule-based: check for numerical contradictions
        score = 100.0
        deductions: list[str] = []

        # Extract all numbers/percentages
        numbers = re.findall(r"(\d+(?:\.\d+)?)\s*%", body)
        if len(numbers) > 1:
            # Check for contradictory percentage claims in same context
            nums = [float(n) for n in numbers]
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    if abs(nums[i] - nums[j]) < 5:
                        continue  # Close numbers, likely same stat
                    # If two very different percentages describe "same thing" sections
                    pass  # Would need deeper NLP; skip for now

        # LLM-based consistency check on key sections
        key_sections = []
        for section_name in ("核心发现", "用户痛点深度分析", "机会与建议"):
            m = re.search(
                rf"##[^#]*{section_name}.*?(?=##|\Z)",
                body,
                re.DOTALL,
            )
            if m:
                key_sections.append(m.group(0)[:500])

        if len(key_sections) >= 2:
            combined = "\n---\n".join(key_sections)
            try:
                resp = await self._complete(
                    [
                        {
                            "role": "system",
                            "content": (
                                "检查以下报告章节之间是否存在逻辑矛盾或不一致。\n"
                                '返回JSON：{"consistent": true/false, '
                                '"score": 0-100, "issues": ["矛盾描述1", ...]}\n'
                                "如果没有矛盾，score应为90-100。"
                            ),
                        },
                        {"role": "user", "content": combined[:2500]},
                    ],
                    temperature=0.05,
                    max_tokens=500,
                )
                raw = resp.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```\w*\n?", "", raw)
                    raw = re.sub(r"\n?```$", "", raw)
                result = json.loads(raw)
                if self._strict:
                    if not isinstance(result, dict):
                        raise VerificationStageError("consistency", "response is not a JSON object")
                    if not isinstance(result.get("score"), (int, float)):
                        raise VerificationStageError("consistency", "score is missing or invalid")
                    if not 0 <= float(result["score"]) <= 100:
                        raise VerificationStageError("consistency", "score is outside 0-100")
                    if not isinstance(result.get("issues", []), list):
                        raise VerificationStageError("consistency", "issues is not a list")
                llm_score = float(result.get("score", 80))
                score = (score + llm_score) / 2
                if result.get("issues"):
                    for issue in result["issues"]:
                        deductions.append(issue)
            except Exception as e:
                if self._strict:
                    if isinstance(e, VerificationStageError):
                        raise
                    raise VerificationStageError("consistency", str(e)) from e
                logger.warning("consistency_check_failed", error=str(e))

        return max(0, min(100, score))

    # ── Step 6: Source Reliability ──

    def _assess_source_reliability(self, sources: list[dict], report_meta: dict) -> float:
        """Score source quality based on platform, volume, and diversity."""
        if not sources:
            return 30.0  # Low score if no sources

        # Platform quality
        platform_scores = []
        for s in sources:
            p = s.get("platform", "unknown").lower()
            platform_scores.append(PLATFORM_RELIABILITY.get(p, 0.4))

        avg_platform = sum(platform_scores) / len(platform_scores)

        # Volume bonus: more sources = more reliable
        volume_bonus = min(15, len(sources) * 1.5)

        # Diversity bonus: multiple platforms
        unique_platforms = len(set(s.get("platform", "unknown") for s in sources))
        diversity_bonus = min(10, unique_platforms * 5)

        # Sentiment diversity (mix of strong/moderate is healthy)
        sentiments = set(s.get("sentiment", "moderate") for s in sources)
        sentiment_bonus = 5 if len(sentiments) > 1 else 0

        raw = (avg_platform * 70) + volume_bonus + diversity_bonus + sentiment_bonus
        return min(100, max(0, raw))

    # ── Step 7: Score Aggregation ──

    def _aggregate(self, claims: list[Claim], consistency: float, source_reliability: float) -> VerificationOutput:
        output = VerificationOutput()
        output.claims = claims
        output.consistency_score = round(consistency, 1)
        output.source_reliability_score = round(source_reliability, 1)

        if not claims:
            output.fact_check_score = 50.0  # Neutral if no extractable claims
        else:
            verdict_scores = {
                "supported": 100,
                "partially": 60,
                "unverifiable": 40,
                "contradicted": 15,
                "hallucination": 0,
            }
            claim_scores = []
            for c in claims:
                base = verdict_scores.get(c.verdict, 40)
                weighted = base * c.confidence + 50 * (1 - c.confidence)
                claim_scores.append(weighted)
            output.fact_check_score = round(sum(claim_scores) / len(claim_scores), 1)

        output.hallucination_count = sum(1 for c in claims if c.verdict == "hallucination")
        output.flagged_count = sum(1 for c in claims if c.verdict in ("hallucination", "contradicted"))

        # Weighted overall: fact-check 45%, consistency 30%, source 25%
        output.overall_score = round(
            output.fact_check_score * 0.45 + output.consistency_score * 0.30 + output.source_reliability_score * 0.25,
            1,
        )

        return output

    # ── Step 8: Suggestion Generation ──

    def _generate_suggestions(self, claims: list[Claim]) -> list[dict[str, str]]:
        suggestions = []
        for c in claims:
            if c.verdict in ("hallucination", "contradicted"):
                suggestions.append(
                    {
                        "type": "correction",
                        "claim": c.text,
                        "verdict": c.verdict,
                        "reason": c.evidence or "该声明与来源数据不符",
                        "action": "建议删除或修正该声明，确保与原始数据一致",
                    }
                )
            elif c.verdict == "partially":
                suggestions.append(
                    {
                        "type": "review",
                        "claim": c.text,
                        "verdict": c.verdict,
                        "reason": c.evidence or "部分内容缺乏数据支撑",
                        "action": "建议补充具体来源或限定表述范围",
                    }
                )
        return suggestions


_verifier: ContentVerifier | None = None


def get_verifier() -> ContentVerifier:
    global _verifier
    if _verifier is None:
        _verifier = ContentVerifier()
    return _verifier
