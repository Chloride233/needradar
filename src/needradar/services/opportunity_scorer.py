from __future__ import annotations

import json
from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.models.opportunity import ProjectOpportunity
from needradar.schemas.schemas import ScoreDimensions, TractionSignal

# Scoring weights: vibe_code(35%) + demand(30%) + feasibility(20%) + freshness(15%)
_SCORE_WEIGHTS = (0.35, 0.30, 0.20, 0.15)

_prompts_cache: dict | None = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is None:
        path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts.yaml"
        with open(path, encoding="utf-8") as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


class OpportunityScorer:
    """Scores requirement clusters for vibe-code suitability using LLM + heuristics."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _get_requirements(self, keyword: str) -> list[dict]:
        from needradar.services.vault_store import vault
        results, _ = vault.search("需求", keyword=keyword, page_size=200)
        return results

    def _cluster(self, requirements: list[dict]) -> list[list[dict]]:
        """Lightweight keyword-overlap clustering. Max 8 clusters."""
        if len(requirements) <= 3:
            return [requirements] if requirements else []

        clusters: list[list[dict]] = []
        used: set[int] = set()
        for i, req in enumerate(requirements):
            if i in used:
                continue
            cluster = [req]
            used.add(i)
            words_a = {w for w in req.get("标题", "").lower().split() if len(w) >= 3}
            for j, other in enumerate(requirements):
                if j in used:
                    continue
                words_b = {w for w in other.get("标题", "").lower().split() if len(w) >= 3}
                if words_a & words_b:
                    cluster.append(other)
                    used.add(j)
            clusters.append(cluster)

        if len(clusters) > 8:
            clusters.sort(key=len, reverse=True)
            for i in range(8, len(clusters)):
                clusters[7].extend(clusters[i])
            clusters = clusters[:8]
        return clusters

    def _heuristic_score(self, titles: list[str]) -> ScoreDimensions:
        """Fallback scoring without LLM, based on keyword detection."""
        combined = " ".join(titles).lower()
        if any(kw in combined for kw in ["ios", "android", "mobile"]):
            vibe = 50.0
        elif any(kw in combined for kw in ["kernel", "driver", "firmware"]):
            vibe = 20.0
        elif any(kw in combined for kw in ["cli", "command", "terminal", "shell"]):
            vibe = 75.0
        elif any(kw in combined for kw in ["web", "app", "dashboard", "browser", "ui"]):
            vibe = 85.0
        else:
            vibe = 60.0

        demand = min(len(titles) * 12.0, 100.0)
        w = _SCORE_WEIGHTS
        overall = round(vibe * w[0] + demand * w[1] + 70 * w[2] + 50 * w[3], 1)
        return ScoreDimensions(
            vibe_code_suitability=vibe, demand_intensity=demand,
            technical_feasibility=70.0, market_freshness=50.0, overall=overall,
        )

    async def _llm_score(self, titles: list[str], descriptions: list[str]) -> ScoreDimensions:
        """LLM-based scoring for vibe-code suitability."""
        prompts = _load_prompts()
        scoring_prompt = prompts.get("vibe_code_scoring", "")
        if not scoring_prompt:
            return self._heuristic_score(titles)

        combined = "\n".join(f"- {t}: {d[:200]}" for t, d in zip(titles[:10], descriptions[:10]))
        try:
            from needradar.llm.provider import llm

            class _ScoreResult(BaseModel):
                vibe_code_suitability: int = 50
                technical_feasibility: int = 50
                market_freshness: int = 50
                reasoning: str = ""

            result = await llm.extract_structured(
                prompt=f"{scoring_prompt}\n\n需求列表:\n{combined}",
                text="请评估这个需求集群的vibe-code适配度",
                schema=_ScoreResult,
            )
            demand = min(len(titles) * 10.0, 100.0)
            scores = ScoreDimensions(
                vibe_code_suitability=float(getattr(result, 'vibe_code_suitability', 50)),
                demand_intensity=demand,
                technical_feasibility=float(getattr(result, 'technical_feasibility', 50)),
                market_freshness=float(getattr(result, 'market_freshness', 50)),
            )
        except (ValueError, ConnectionError, TimeoutError, RuntimeError) as e:
            logger.warning("llm_scoring_failed", error=str(e))
            scores = self._heuristic_score(titles)

        w = _SCORE_WEIGHTS
        scores.overall = round(
            scores.vibe_code_suitability * w[0] + scores.demand_intensity * w[1]
            + scores.technical_feasibility * w[2] + scores.market_freshness * w[3], 1)
        return scores

    def _build_traction(self, cluster: list[dict]) -> list[TractionSignal]:
        sentiment_map = {"strong": 1.0, "moderate": 0.6, "mild": 0.3}
        src_counts: dict[str, int] = {}
        src_quotes: dict[str, list[str]] = {}
        src_sentiments: dict[str, list[float]] = {}
        for req in cluster:
            src = req.get("来源平台", "unknown")
            src_counts[src] = src_counts.get(src, 0) + 1
            src_quotes.setdefault(src, []).append(req.get("标题", ""))
            src_sentiments.setdefault(src, []).append(
                sentiment_map.get(req.get("情感倾向", "moderate"), 0.5)
            )
        signals = []
        for src, count in sorted(src_counts.items(), key=lambda x: -x[1]):
            sents = src_sentiments.get(src, [0.5])
            quotes = src_quotes.get(src, [""])
            signals.append(TractionSignal(
                source=src, mention_count=count,
                sentiment_strength=round(sum(sents) / len(sents), 2),
                representative_quote=quotes[0],
            ))
        return signals

    async def score_keyword(self, keyword: str) -> list[ProjectOpportunity]:
        requirements = await self._get_requirements(keyword)
        if not requirements:
            logger.info("no_requirements_for_scoring", keyword=keyword)
            return []

        clusters = self._cluster(requirements)
        logger.info("clustered", keyword=keyword, clusters=len(clusters), requirements=len(requirements))

        opportunities: list[ProjectOpportunity] = []
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            titles = [r.get("标题", "") for r in cluster]
            descriptions = [r.get("_body", "") for r in cluster]
            scores = await self._llm_score(titles, descriptions)
            traction = self._build_traction(cluster)
            req_ids = titles

            opp = ProjectOpportunity(
                keyword=keyword, title=titles[0][:300],
                description=f"基于 {len(cluster)} 条相关需求聚合",
                scores_json=json.dumps(scores.model_dump(), ensure_ascii=False),
                traction_json=json.dumps([t.model_dump() for t in traction], ensure_ascii=False),
                source_req_ids_json=json.dumps(req_ids, ensure_ascii=False),
                status="scored",
            )
            self._db.add(opp)
            opportunities.append(opp)

        await self._db.flush()
        for opp in opportunities:
            await self._link_contains(opp)
        logger.info("scoring_done", keyword=keyword, count=len(opportunities))
        return opportunities

    async def _link_contains(self, opp: ProjectOpportunity) -> None:
        """Create EntityLink rows: opportunity --[contains]--> requirements."""
        try:
            from needradar.models.link import LinkType
            from needradar.schemas.schemas import EntityLinkCreateRequest
            from needradar.services.link_service import EntityLinkService

            req_ids = json.loads(opp.source_req_ids_json)
            if not req_ids:
                return
            svc = EntityLinkService(self._db)
            await svc.batch_create([
                EntityLinkCreateRequest(
                    source_type="opportunity", source_id=str(opp.id),
                    link_type=LinkType.CONTAINS, target_type="requirement", target_id=title,
                )
                for title in req_ids
            ])
        except Exception as e:
            logger.warning("entity_link_failed", link_type="contains", error=str(e))

    async def list_opportunities(
        self, keyword: str = "", min_score: float = 0, page: int = 1, page_size: int = 20,
    ) -> tuple[list[ProjectOpportunity], int]:
        query = select(ProjectOpportunity)
        count_query = select(ProjectOpportunity.id)
        if keyword:
            query = query.where(ProjectOpportunity.keyword == keyword)
            count_query = count_query.where(ProjectOpportunity.keyword == keyword)

        result = await self._db.execute(count_query)
        total = len(result.scalars().all())

        query = query.order_by(ProjectOpportunity.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self._db.execute(query)
        rows = list(result.scalars().all())

        # Note: min_score filtering is post-query because scores are stored as JSON.
        # Materialize a score column in the DB if filtering becomes a bottleneck.
        if min_score > 0:
            rows = [r for r in rows if json.loads(r.scores_json).get("overall", 0) >= min_score]
        return rows, total

    async def get_opportunity(self, opportunity_id: int) -> ProjectOpportunity | None:
        result = await self._db.execute(
            select(ProjectOpportunity).where(ProjectOpportunity.id == opportunity_id)
        )
        return result.scalar_one_or_none()
