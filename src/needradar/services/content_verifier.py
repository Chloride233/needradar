from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any

from loguru import logger

from needradar.llm.provider import llm
from needradar.services.vault_store import vault


# ── Data structures ──

@dataclass
class Claim:
    text: str
    section: str = ""
    verdict: str = "unverifiable"   # supported / partially / unverifiable / contradicted / hallucination
    confidence: float = 0.0         # 0-1
    evidence: str = ""
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class VerificationOutput:
    overall_score: float = 0.0       # 0-100
    fact_check_score: float = 0.0
    consistency_score: float = 0.0
    source_reliability_score: float = 0.0
    claims: list[Claim] = field(default_factory=list)
    suggestions: list[dict[str, str]] = field(default_factory=list)
    hallucination_count: int = 0
    flagged_count: int = 0


# ── Platform reliability weights ──

PLATFORM_RELIABILITY = {
    "github": 0.85,
    "stackoverflow": 0.80,
    "juejin": 0.70,
    "unknown": 0.40,
}


# ── Core verifier ──

class ContentVerifier:
    """Multi-dimensional hallucination detection and content verification."""

    def __init__(self) -> None:
        self._usage_records: list[dict] = []

    def _pop_usage(self) -> None:
        u = llm.pop_last_usage()
        if u:
            self._usage_records.append(u)

    async def verify_report(self, report_title: str) -> VerificationOutput:
        self._usage_records = []

        # 1. Load report and source data
        path = vault.find_by_title("初稿", report_title)
        if not path:
            logger.warning("verify_report_not_found", title=report_title)
            return VerificationOutput()
        meta, body = vault.read(path)
        keyword = ""
        kws = meta.get("关键词", [])
        if isinstance(kws, list) and kws:
            keyword = str(kws[0])

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

    def _split_sections(self, body: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        current_header = "preamble"
        current_lines: list[str] = []
        for line in body.split("\n"):
            if re.match(r'^#{1,4}\s', line):
                if current_lines:
                    sections[current_header] = "\n".join(current_lines)
                current_header = re.sub(r'^#{1,4}\s+', '', line).strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections[current_header] = "\n".join(current_lines)
        return sections

    async def _llm_extract_claims_batch(self, body: str) -> list[Claim]:
        """Extract claims from entire report body in a single call."""
        if len(body.strip()) < 50:
            return []
        try:
            resp = await llm.complete([
                {
                    "role": "system",
                    "content": (
                        "你是事实核查专家。从报告中提取所有可验证的事实性声明。\n"
                        "每条声明应是一个可以用真/假/部分真来验证的具体论断。\n"
                        "忽略主观观点和推荐建议，只提取事实性内容。\n\n"
                        "以JSON数组返回，格式：[{\"text\": \"声明\", \"section\": \"所在章节名\"}]\n"
                        "最多提取20条。无声明返回 []。"
                    ),
                },
                {"role": "user", "content": body[:4000]},
            ], temperature=0.1, max_tokens=2000)
            raw = resp.strip()
            if raw.startswith("```"):
                raw = re.sub(r'^```\w*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)
            items = json.loads(raw)
            if not isinstance(items, list):
                items = []
            return [
                Claim(
                    text=item["text"],
                    section=item.get("section", ""),
                )
                for item in items
                if isinstance(item, dict) and "text" in item and len(item["text"]) > 5
            ]
        except Exception as e:
            logger.warning("claim_extraction_failed", error=str(e))
            return []

    def _rule_based_claims(self, body: str) -> list[Claim]:
        """Extract claims from bold/highlighted text patterns."""
        claims = []
        seen = set()
        # Bold text in numbered items: 1. **claim text**
        for m in re.finditer(r'\d+\.\s*\*\*(.{10,150}?)\*\*', body):
            text = m.group(1).strip().rstrip('：:')
            if text not in seen:
                seen.add(text)
                claims.append(Claim(text=text, section="核心发现"))
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
            m = re.search(r'\[\[.*?/(.*?)\|', ref)
            if m:
                title = m.group(1).strip()
            else:
                title = ref.strip('[]|')
            src = vault.find_by_title("需求", title)
            if src:
                meta, body = vault.read(src)
                sources.append({
                    "title": meta.get("标题", title),
                    "platform": meta.get("来源平台", "unknown"),
                    "sentiment": meta.get("情感倾向", "moderate"),
                    "content": (body or meta.get("_body", ""))[:800],
                })
        return sources

    # ── Step 4: Fact-Checking ──

    async def _fact_check_claims(self, claims: list[Claim], sources: list[dict]) -> list[Claim]:
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
            f"[{s['platform']}] {s['title']}: {s['content'][:200]}"
            for s in sources[:15]
        )

        # Send all claims in one call — shared source_summary prefix gets cached
        # Split into batches of 12 if too many claims
        for i in range(0, len(claims), 12):
            batch = claims[i:i + 12]
            await self._llm_fact_check_batch(batch, source_summary)

        return claims

    async def _llm_fact_check_batch(self, claims: list[Claim], source_summary: str) -> None:
        claim_list = "\n".join(f"{i+1}. {c.text}" for i, c in enumerate(claims))
        try:
            resp = await llm.complete([
                {
                    "role": "system",
                    "content": (
                        "你是事实核查验证引擎。根据提供的来源数据，逐一验证以下声明的准确性。\n\n"
                        "对每条声明返回JSON：\n"
                        "[{\"idx\": 1, \"verdict\": \"supported|partially|unverifiable|contradicted|hallucination\", "
                        "\"confidence\": 0.0-1.0, \"evidence\": \"支持/反驳的依据简述\", "
                        "\"flags\": [\"风险标记列表\"]}]\n\n"
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
            ], temperature=0.05, max_tokens=2000)

            raw = resp.strip()
            if raw.startswith("```"):
                raw = re.sub(r'^```\w*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)
            results = json.loads(raw)
            if not isinstance(results, list):
                return

            for r in results:
                idx = r.get("idx", 0) - 1
                if 0 <= idx < len(claims):
                    claims[idx].verdict = r.get("verdict", "unverifiable")
                    claims[idx].confidence = min(1.0, max(0.0, float(r.get("confidence", 0.5))))
                    claims[idx].evidence = r.get("evidence", "")
                    claims[idx].risk_flags = r.get("flags", [])
        except Exception as e:
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
        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*%', body)
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
                rf'##[^#]*{section_name}.*?(?=##|\Z)',
                body, re.DOTALL,
            )
            if m:
                key_sections.append(m.group(0)[:500])

        if len(key_sections) >= 2:
            combined = "\n---\n".join(key_sections)
            try:
                resp = await llm.complete([
                    {
                        "role": "system",
                        "content": (
                            "检查以下报告章节之间是否存在逻辑矛盾或不一致。\n"
                            "返回JSON：{\"consistent\": true/false, "
                            "\"score\": 0-100, \"issues\": [\"矛盾描述1\", ...]}\n"
                            "如果没有矛盾，score应为90-100。"
                        ),
                    },
                    {"role": "user", "content": combined[:2500]},
                ], temperature=0.05, max_tokens=500)
                raw = resp.strip()
                if raw.startswith("```"):
                    raw = re.sub(r'^```\w*\n?', '', raw)
                    raw = re.sub(r'\n?```$', '', raw)
                result = json.loads(raw)
                llm_score = float(result.get("score", 80))
                score = (score + llm_score) / 2
                if result.get("issues"):
                    for issue in result["issues"]:
                        deductions.append(issue)
            except Exception as e:
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
            output.fact_check_score * 0.45 +
            output.consistency_score * 0.30 +
            output.source_reliability_score * 0.25,
            1,
        )

        return output

    # ── Step 8: Suggestion Generation ──

    def _generate_suggestions(self, claims: list[Claim]) -> list[dict[str, str]]:
        suggestions = []
        for c in claims:
            if c.verdict in ("hallucination", "contradicted"):
                suggestions.append({
                    "type": "correction",
                    "claim": c.text,
                    "verdict": c.verdict,
                    "reason": c.evidence or "该声明与来源数据不符",
                    "action": "建议删除或修正该声明，确保与原始数据一致",
                })
            elif c.verdict == "partially":
                suggestions.append({
                    "type": "review",
                    "claim": c.text,
                    "verdict": c.verdict,
                    "reason": c.evidence or "部分内容缺乏数据支撑",
                    "action": "建议补充具体来源或限定表述范围",
                })
        return suggestions


_verifier: ContentVerifier | None = None


def get_verifier() -> ContentVerifier:
    global _verifier
    if _verifier is None:
        _verifier = ContentVerifier()
    return _verifier
