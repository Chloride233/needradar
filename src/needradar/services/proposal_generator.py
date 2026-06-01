"""Generate executable project proposals from scored opportunities."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.llm.provider import llm
from needradar.models.opportunity import ProjectOpportunity
from needradar.models.proposal import ProjectProposal
from needradar.services.vault_store import vault

_prompts_cache: dict | None = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is None:
        path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts.yaml"
        with open(path, encoding="utf-8") as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


def _build_claude_prompt(result) -> str:
    title = getattr(result, 'title', '')
    problem = getattr(result, 'problem_statement', '')
    target = getattr(result, 'target_user', '')
    mvp = getattr(result, 'mvp_scope', [])
    stack = getattr(result, 'suggested_stack', {})

    mvp_lines = "\n".join(
        f"- [{m.get('priority', 'P1')}] {m.get('name', '')}: {m.get('description', '')}"
        for m in mvp
    )
    return f"""# Project: {title}

## Problem
{problem}

## Target Users
{target}

## MVP Scope
{mvp_lines}

## Suggested Tech Stack
- Frontend: {stack.get('frontend', 'TBD')}
- Backend: {stack.get('backend', 'TBD')}
- Database: {stack.get('database', 'TBD')}
- Hosting: {stack.get('hosting', 'TBD')}
- Why: {stack.get('rationale', 'Minimal maintenance')}

## Estimated Effort
~{getattr(getattr(result, 'effort_estimate', {}), 'total_hours', 40)} hours

## Build Instructions
Scaffold this project with {stack.get('frontend', 'Vue')} + {stack.get('backend', 'FastAPI')}.
Start with the data model, then implement the core user flow.
"""


def _build_vault_body(proposal, result) -> str:
    title = getattr(result, 'title', proposal.title)
    problem = getattr(result, 'problem_statement', '')
    target = getattr(result, 'target_user', '')
    mvp = getattr(result, 'mvp_scope', [])
    stack = getattr(result, 'suggested_stack', {})
    effort = getattr(result, 'effort_estimate', {})
    risks = getattr(result, 'risks', [])
    monetization = getattr(result, 'monetization_hint', '')

    mvp_section = "\n".join(
        f"- **[{m.get('priority', 'P1')}] {m.get('name', '')}**: {m.get('description', '')}"
        for m in mvp
    )
    risk_section = "\n".join(f"- {r}" for r in risks) if risks else "待分析"

    return f"""# {title}

## 问题陈述
{problem}

## 目标用户
{target}

## MVP 功能
{mvp_section}

## 技术栈
| 层级 | 选型 |
|------|------|
| 前端 | {stack.get('frontend', 'TBD')} |
| 后端 | {stack.get('backend', 'TBD')} |
| 数据库 | {stack.get('database', 'TBD')} |
| 部署 | {stack.get('hosting', 'TBD')} |

> {stack.get('rationale', '')}

## 工作量
{effort.get('total_hours', 'N/A')} 小时: {json.dumps(effort.get('breakdown', {}), ensure_ascii=False)}

## 风险
{risk_section}

## 变现
{monetization}
"""


class ProposalGenerator:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def generate(self, opportunity_id: int) -> ProjectProposal | None:
        opp = await self._db.get(ProjectOpportunity, opportunity_id)
        if not opp:
            return None

        prompts = _load_prompts()
        gen_prompt = prompts.get("proposal_generation", "")
        if not gen_prompt:
            return None

        try:
            scores = json.loads(opp.scores_json)
            traction = json.loads(opp.traction_json)
            req_ids = json.loads(opp.source_req_ids_json)
        except json.JSONDecodeError:
            scores, traction, req_ids = {}, [], []

        context = (
            f"关键词: {opp.keyword}\n机会: {opp.title}\n描述: {opp.description}\n"
            f"评分: {json.dumps(scores, ensure_ascii=False)}\n"
            f"热度: {json.dumps(traction, ensure_ascii=False)}\n"
            f"需求: {', '.join(req_ids[:20])}"
        )

        try:
            class _ProposalResult(BaseModel):
                title: str = ""
                problem_statement: str = ""
                target_user: str = ""
                mvp_scope: list = []
                suggested_stack: dict = {}
                effort_estimate: dict = {}
                risks: list = []
                monetization_hint: str = ""

            result = await llm.extract_structured(
                prompt=gen_prompt, text=context, schema=_ProposalResult,
            )
        except (ValueError, ConnectionError, TimeoutError, RuntimeError) as e:
            logger.warning("proposal_llm_failed", error=str(e))
            result = _ProposalResult(
                title=opp.title, problem_statement=opp.description,
                target_user="独立开发者",
                mvp_scope=[{"name": "核心功能", "priority": "P0", "description": "TBD"}],
                suggested_stack={"frontend": "Vue 3", "backend": "FastAPI",
                                 "database": "SQLite", "hosting": "Vercel",
                                 "rationale": "最低维护成本"},
                effort_estimate={"total_hours": 40, "breakdown": {"前端": 15, "后端": 15, "数据库": 5, "部署": 3, "测试": 2}},
                risks=["需验证需求真实性"], monetization_hint="开源 + SaaS",
            )

        claude_prompt = _build_claude_prompt(result)
        effort = getattr(result, 'effort_estimate', {})

        proposal = ProjectProposal(
            opportunity_id=opportunity_id, keyword=opp.keyword,
            title=getattr(result, 'title', opp.title)[:300],
            problem_statement=getattr(result, 'problem_statement', ''),
            target_user=getattr(result, 'target_user', ''),
            mvp_scope_json=json.dumps(getattr(result, 'mvp_scope', []), ensure_ascii=False),
            suggested_stack_json=json.dumps(getattr(result, 'suggested_stack', {}), ensure_ascii=False),
            effort_estimate_hours=effort.get("total_hours", 0),
            effort_breakdown_json=json.dumps(effort, ensure_ascii=False),
            traction_signals_json=opp.traction_json,
            claude_prompt=claude_prompt,
            risks_json=json.dumps(getattr(result, 'risks', []), ensure_ascii=False),
            status="draft",
        )
        self._db.add(proposal)
        await self._db.flush()

        await self._link_generates(opportunity_id, proposal)

        try:
            body = _build_vault_body(proposal, result)
            filepath = vault.write("初稿", proposal.title, {
                "标题": proposal.title, "阶段": "初稿",
                "关键词": [proposal.keyword],
                "创建时间": str(proposal.created_at.date()) if proposal.created_at else "",
                "关联参考": [], "发布平台": "内部",
            }, body)
            proposal.vault_path = str(filepath)
        except Exception as e:
            logger.warning("proposal_vault_write_failed", error=str(e))

        logger.info("proposal_generated", title=proposal.title)
        return proposal

    async def _link_generates(self, opportunity_id: int, proposal: ProjectProposal) -> None:
        """Create EntityLink: opportunity --[generates]--> proposal."""
        try:
            from needradar.schemas.schemas import EntityLinkCreateRequest
            from needradar.models.link import LinkType
            from needradar.services.link_service import EntityLinkService

            svc = EntityLinkService(self._db)
            await svc.create(EntityLinkCreateRequest(
                source_type="opportunity", source_id=str(opportunity_id),
                link_type=LinkType.GENERATES, target_type="proposal", target_id=str(proposal.id),
                metadata={"title": proposal.title},
            ))
        except Exception as e:
            logger.warning("entity_link_failed", link_type="generates", error=str(e))

    async def list_proposals(self, keyword: str = "", page: int = 1, page_size: int = 20):
        query = select(ProjectProposal)
        count_q = select(ProjectProposal.id)
        if keyword:
            query = query.where(ProjectProposal.keyword == keyword)
            count_q = count_q.where(ProjectProposal.keyword == keyword)

        result = await self._db.execute(count_q)
        total = len(result.scalars().all())

        query = query.order_by(ProjectProposal.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self._db.execute(query)
        return list(result.scalars().all()), total

    async def get_proposal(self, proposal_id: int) -> ProjectProposal | None:
        result = await self._db.execute(
            select(ProjectProposal).where(ProjectProposal.id == proposal_id)
        )
        return result.scalar_one_or_none()
