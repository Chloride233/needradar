from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import yaml
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.config import settings
from needradar.crawlers.factory import create_crawler
from needradar.llm.provider import llm
from needradar.models.crawl_task import CrawlTask, TaskStatus
from needradar.models.fingerprint import CrawlFingerprint
from needradar.models.llm_usage import LLMUsage
from needradar.schemas.schemas import ExtractedRequirement, RawDiscussionItem
from needradar.services.vault_store import vault

MAX_PIPELINE_SECONDS = 30 * 60

_prompts_cache: dict | None = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is None:
        path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts.yaml"
        with open(path, encoding="utf-8") as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


def invalidate_prompts_cache() -> None:
    global _prompts_cache
    _prompts_cache = None


class AnalysisService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._vector_store = None

    def _get_vector_store(self):
        if self._vector_store is None:
            from needradar.vector import create_vector_store
            self._vector_store = create_vector_store()
        return self._vector_store

    async def _safe_flush(self, retries: int = 3, delay: float = 0.5) -> None:
        for attempt in range(retries):
            try:
                await self._db.flush()
                return
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(delay * (attempt + 1))
                else:
                    raise

    def _build_system_prompt(self, task_prompt: str) -> str:
        prompts = _load_prompts()
        rules = prompts.get("_system_rules", "")
        return f"{rules}\n\n{task_prompt}" if rules else task_prompt

    async def _load_known_urls(self, keyword: str, platform: str) -> set[str]:
        result = await self._db.execute(
            select(CrawlFingerprint.source_url).where(
                CrawlFingerprint.keyword == keyword,
                CrawlFingerprint.platform == platform,
            )
        )
        return {row[0] for row in result.all()}

    async def _save_fingerprints(self, keyword: str, platform: str, items: list[RawDiscussionItem]) -> None:
        for item in items:
            self._db.add(CrawlFingerprint(
                keyword=keyword,
                platform=platform,
                source_url=item.source_url,
            ))

    async def _filter_new_items(
        self, keyword: str, platform: str, items: list[RawDiscussionItem],
    ) -> tuple[list[RawDiscussionItem], int]:
        known = await self._load_known_urls(keyword, platform)
        new_items = [item for item in items if item.source_url not in known]
        return new_items, len(items) - len(new_items)

    async def run_pipeline(self, keyword: str, platforms: list[str], existing_task_ids: list[int] | None = None) -> list[CrawlTask]:
        if existing_task_ids:
            result = await self._db.execute(
                select(CrawlTask).where(CrawlTask.id.in_(existing_task_ids))
            )
            tasks = list(result.scalars().all())
        else:
            tasks: list[CrawlTask] = []
            for platform in platforms:
                task = CrawlTask(keyword=keyword, platform=platform, status=TaskStatus.PENDING)
                self._db.add(task)
                tasks.append(task)
            await self._safe_flush()

        # Phase 1: Crawl all platforms concurrently
        crawl_results: dict[int, list] = {}
        crawlers: dict[int, object] = {}

        async def _crawl_one(task: CrawlTask) -> None:
            crawler = create_crawler(task.platform)
            crawlers[task.id] = crawler
            try:
                task.status = TaskStatus.RUNNING
                await self._safe_flush()
                await self._db.commit()

                raw_items = await asyncio.wait_for(crawler.crawl(keyword), timeout=MAX_PIPELINE_SECONDS)
                task.total_items = len(raw_items)

                # Incremental filter: skip already-seen URLs
                new_items, skipped = await self._filter_new_items(keyword, task.platform, raw_items)
                task.new_items = len(new_items)
                task.skipped_items = skipped
                await self._save_fingerprints(keyword, task.platform, new_items)

                crawl_results[task.id] = new_items
                logger.info("crawl_done", platform=task.platform, total=len(raw_items), new=len(new_items), skipped=skipped)
            except asyncio.TimeoutError:
                task.status = TaskStatus.FAILED
                task.error_message = "任务执行超时（30分钟限制）"
                logger.error("pipeline_timeout", platform=task.platform)
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)[:2000]
                logger.error("crawl_failed", platform=task.platform, error=str(e))

        await asyncio.gather(*[_crawl_one(t) for t in tasks])
        await self._safe_flush()
        await self._db.commit()

        # Phase 2: Extract and store per task (sequential — shares LLM rate limit)
        for task in tasks:
            raw_items = crawl_results.get(task.id, [])
            if not raw_items or task.status == TaskStatus.FAILED:
                continue

            remaining = MAX_PIPELINE_SECONDS - 120
            for item in raw_items:
                if remaining <= 0:
                    logger.warning("pipeline_timeout", platform=task.platform, processed=raw_items.index(item))
                    task.error_message = f"处理超时，已处理 {raw_items.index(item)}/{len(raw_items)} 条"
                    break
                start_t = asyncio.get_event_loop().time()
                try:
                    await self._extract_and_store(keyword, item)
                except Exception as e:
                    logger.warning("item_extract_failed", url=item.source_url, error=str(e))
                remaining -= asyncio.get_event_loop().time() - start_t

            if not task.error_message:
                task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.COMPLETED

        # Close all crawlers
        for crawler in crawlers.values():
            try:
                await crawler.close()
            except Exception:
                pass

        await self._safe_flush()
        await self._db.commit()
        return tasks

    async def _extract_and_store(self, keyword: str, item: RawDiscussionItem) -> Path | None:
        prompts = _load_prompts()
        extraction_prompt = prompts.get("requirement_extraction", "")
        full_prompt = self._build_system_prompt(extraction_prompt)

        text = f"讨论标题：{item.title}\n\n讨论内容：\n{item.content}"
        extracted: ExtractedRequirement = await llm.extract_structured(
            prompt=full_prompt,
            text=text,
            schema=ExtractedRequirement,
        )
        self._record_usage()

        # Embedding-based dedup via ChromaDB
        embed_text = f"{extracted.title}\n{extracted.description}"
        try:
            vs = self._get_vector_store()
            results = await vs.query([embed_text], n_results=1)
            if results and results[0].score >= settings.similarity_threshold:
                match_id = results[0].id
                existing = vault.find_by_title("需求", match_id)
                if existing:
                    meta, _ = vault.read(existing)
                    meta["提及次数"] = meta.get("提及次数", 1) + 1
                    meta.setdefault("相似来源", []).append(item.source_url)
                    vault.update_frontmatter(existing, {"提及次数": meta["提及次数"], "相似来源": meta["相似来源"]})
                    logger.debug("vector_dedup", title=extracted.title, match=match_id, score=results[0].score)
                    return None
        except Exception as e:
            logger.warning("embedding_dedup_failed, falling back to title", error=str(e))
            existing = vault.find_by_title("需求", extracted.title)
            if existing:
                meta, _ = vault.read(existing)
                meta["提及次数"] = meta.get("提及次数", 1) + 1
                vault.update_frontmatter(existing, {"提及次数": meta["提及次数"]})
                logger.debug("title_dedup", title=extracted.title)
                return None

        from datetime import date
        meta = {
            "标题": extracted.title,
            "阶段": "需求",
            "来源平台": item.platform,
            "来源URL": item.source_url,
            "关键词": [keyword],
            "情感倾向": extracted.sentiment.value,
            "情绪极性": extracted.emotion.value,
            "置信度": extracted.confidence,
            "提及次数": 1,
            "创建时间": str(date.today()),
            "关联参考": [],
            "发布平台": "内部",
        }
        body = f"## 需求描述\n\n{extracted.description}\n\n## 用户痛点\n\n{extracted.pain_point}\n\n## 使用场景\n\n{extracted.use_case}"
        filepath = vault.write("需求", extracted.title, meta, body)
        logger.info("requirement_stored", title=extracted.title, path=str(filepath))

        # Add to vector store for future dedup
        try:
            await self._get_vector_store().add(
                ids=[extracted.title],
                documents=[embed_text],
                metadatas=[{"platform": item.platform, "keyword": keyword}],
            )
        except Exception as e:
            logger.warning("vector_store_add_failed", error=str(e))

        return filepath

    def _record_usage(self) -> None:
        usage = llm.pop_last_usage()
        if usage:
            self._db.add(LLMUsage(**usage))
