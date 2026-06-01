from __future__ import annotations

import asyncio
from pathlib import Path

import yaml
from loguru import logger

from needradar.schemas.schemas import FilteredItem, NoiseVerdict, RawDiscussionItem

# Patterns for rule-based coarse filtering — fast, no LLM cost
_NON_TECH_KEYWORDS = [
    "股票", "炒股", "基金", "理财", "保险",
    "招聘", "求职", "简历", "面试",
    "相亲", "交友", "约会", "征婚",
    "买房", "租房", "房价", "楼盘",
    "彩票", "中奖", "双色球",
    "医院", "挂号", "处方", "医保",
    "考研", "公务员", "教师资格证",
]


def _rule_filter(item: RawDiscussionItem) -> FilteredItem | None:
    """Fast rule-based filter. Returns None if item passes (not noise)."""
    content = item.content.lower() + " " + item.title.lower()

    # Too short
    if len(content.strip()) < 60:
        return FilteredItem(item=item, verdict=NoiseVerdict.NOISE,
                            reason="内容过短 (<60字符)", confidence=0.95)

    # Too long and repetitive (likely spam/auto-generated)
    if len(content) > 50000:
        return FilteredItem(item=item, verdict=NoiseVerdict.NOISE,
                            reason="内容过长 (>50000字符)", confidence=0.85)

    # Non-tech keywords
    hits = [kw for kw in _NON_TECH_KEYWORDS if kw in content]
    if hits:
        return FilteredItem(item=item, verdict=NoiseVerdict.NOISE,
                            reason=f"包含非技术关键词: {', '.join(hits[:3])}", confidence=0.90)

    # Pure ad/spam detection: high ratio of repeated lines
    lines = [line.strip() for line in item.content.split("\n") if line.strip()]
    if len(lines) > 3:
        unique_ratio = len(set(lines)) / len(lines)
        if unique_ratio < 0.3:
            return FilteredItem(item=item, verdict=NoiseVerdict.NOISE,
                                reason="疑似重复/垃圾内容", confidence=0.85)

    # Item passes rule filter
    return None


class NoiseFilter:
    """Filters crawled items: rule-based (fast) + optional LLM-based (thorough).

    Rule-based filter catches obvious garbage (<60 chars, non-tech keywords,
    spam patterns). LLM filter evaluates whether a discussion represents a
    problem that could be solved by building a software tool.
    """

    def __init__(self, use_llm: bool = False) -> None:
        self._use_llm = use_llm
        self._llm_prompt: str | None = None

    def _load_llm_prompt(self) -> str:
        if self._llm_prompt is None:
            prompts_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts.yaml"
            with open(prompts_path, encoding="utf-8") as f:
                prompts = yaml.safe_load(f)
            self._llm_prompt = prompts.get("noise_filter", "")
        return self._llm_prompt or ""

    async def filter_item(self, item: RawDiscussionItem) -> FilteredItem:
        """Filter a single item. Returns FilteredItem with verdict."""
        # Step 1: Rule filter
        rule_result = _rule_filter(item)
        if rule_result is not None:
            return rule_result

        # Step 2: LLM filter (if enabled)
        if self._use_llm:
            return await self._llm_filter(item)

        # Default: pass rule filter = relevant
        return FilteredItem(item=item, verdict=NoiseVerdict.RELEVANT,
                            reason="规则过滤通过", confidence=0.7)

    async def _llm_filter(self, item: RawDiscussionItem) -> FilteredItem:
        prompt = self._load_llm_prompt()
        if not prompt:
            return FilteredItem(item=item, verdict=NoiseVerdict.RELEVANT,
                                reason="LLM过滤未配置，默认通过", confidence=0.5)

        text = f"标题: {item.title}\n内容: {item.content[:3000]}"
        try:
            from needradar.llm.provider import llm

            result = await llm.extract_structured(
                prompt=prompt,
                text=text,
                schema=FilteredItem,
            )
            return result
        except (ValueError, ConnectionError, TimeoutError, RuntimeError) as e:
            logger.warning("llm_noise_filter_failed, passing through", error=str(e))
            return FilteredItem(item=item, verdict=NoiseVerdict.RELEVANT,
                                reason="LLM过滤失败，默认通过", confidence=0.3)

    async def filter_batch(
        self, items: list[RawDiscussionItem], concurrency: int = 5
    ) -> list[FilteredItem]:
        """Filter a batch of items with concurrency control."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _filter_one(item: RawDiscussionItem) -> FilteredItem:
            async with semaphore:
                return await self.filter_item(item)

        return await asyncio.gather(*[_filter_one(item) for item in items])
