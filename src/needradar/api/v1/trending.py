from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.trending import TrendingProject, TrendingSince
from needradar.services.vault_store import vault

router = APIRouter(prefix="/trending", tags=["trending"])


# ── Schemas ──

class TrendingProjectOut(BaseModel):
    id: int
    full_name: str
    description: str
    language: str
    stars: int
    forks: int
    period_stars: int
    since: str
    contributors: str
    tags: str
    snapshot_date: str
    is_analyzed: bool

    class Config:
        from_attributes = True


class TrendingListResponse(BaseModel):
    items: list[TrendingProjectOut]
    total: int


class TrendingStatsResponse(BaseModel):
    language_distribution: dict[str, int]
    total_projects: int
    snapshots_available: list[str]


class TriggerResponse(BaseModel):
    fetched: int
    new: int
    duplicates: int


# ── Endpoints ──

@router.get("", response_model=TrendingListResponse)
async def list_trending(
    language: str = Query("", description="Filter by programming language"),
    since: str = Query("daily", description="Time range: daily/weekly/monthly"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TrendingProject)
    count_stmt = select(func.count()).select_from(TrendingProject)

    if language:
        stmt = stmt.where(TrendingProject.language == language)
        count_stmt = count_stmt.where(TrendingProject.language == language)
    if since:
        stmt = stmt.where(TrendingProject.since == since)
        count_stmt = count_stmt.where(TrendingProject.since == since)

    stmt = stmt.order_by(TrendingProject.period_stars.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt)
    items = result.scalars().all()

    return TrendingListResponse(
        items=[TrendingProjectOut.model_validate(p) for p in items],
        total=total,
    )


@router.get("/languages", response_model=list[str])
async def get_languages(db: AsyncSession = Depends(get_db)):
    """List all languages seen in trending data."""
    stmt = (
        select(TrendingProject.language)
        .distinct()
        .where(TrendingProject.language != "")
        .order_by(TrendingProject.language)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


@router.get("/stats", response_model=TrendingStatsResponse)
async def trending_stats(
    since: str = Query("daily"),
    db: AsyncSession = Depends(get_db),
):
    # Language distribution
    stmt = (
        select(TrendingProject.language, func.count())
        .where(TrendingProject.since == since)
        .group_by(TrendingProject.language)
        .order_by(func.count().desc())
    )
    result = await db.execute(stmt)
    lang_dist = {row[0] or "unknown": row[1] for row in result.all()}

    # Total
    total = (await db.execute(
        select(func.count()).select_from(TrendingProject).where(TrendingProject.since == since)
    )).scalar() or 0

    # Available snapshot dates
    dates = (await db.execute(
        select(TrendingProject.snapshot_date).distinct().order_by(TrendingProject.snapshot_date.desc()).limit(30)
    )).scalars().all()

    return TrendingStatsResponse(
        language_distribution=lang_dist,
        total_projects=total,
        snapshots_available=dates,
    )


@router.post("/fetch", response_model=TriggerResponse)
async def fetch_trending(
    language: str = Query("", description="Filter by language, empty = all"),
    since: str = Query("daily"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a trending scrape and store results."""
    from needradar.crawlers.github_trending import GitHubTrendingCrawler

    crawler = GitHubTrendingCrawler()
    try:
        raw = await crawler.crawl_trending(language=language, since=since)
    finally:
        await crawler.close()

    if raw:
        from loguru import logger
        logger.info("trending_fetched", count=len(raw), sample_stars=raw[0].get("stars"))

    new_count = 0
    dup_count = 0
    today = str(date.today())

    for proj in raw:
        # Dedup by (full_name, since, snapshot_date)
        exists = (await db.execute(
            select(TrendingProject).where(
                TrendingProject.full_name == proj["full_name"],
                TrendingProject.since == proj["since"],
                TrendingProject.snapshot_date == today,
            )
        )).scalar_one_or_none()

        if exists:
            dup_count += 1
            # Update period_stars if changed
            if exists.period_stars != proj["period_stars"]:
                exists.period_stars = proj["period_stars"]
                exists.stars = proj["stars"]
                exists.forks = proj["forks"]
            continue

        db.add(TrendingProject(**proj))
        new_count += 1

    await db.commit()
    return TriggerResponse(fetched=len(raw), new=new_count, duplicates=dup_count)


@router.post("/fetch-all")
async def fetch_all_trending(db: AsyncSession = Depends(get_db)):
    """Scrape trending for all 3 time ranges (daily + weekly + monthly)."""
    results = {}
    for since in ("daily", "weekly", "monthly"):
        r = await fetch_trending(language="", since=since, db=db)
        results[since] = r.model_dump()
    return results


@router.post("/analyze/{project_id}")
async def analyze_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate topic tags for a trending project using LLM, store to vault."""
    from needradar.llm.provider import llm

    project = (await db.execute(
        select(TrendingProject).where(TrendingProject.id == project_id)
    )).scalar_one_or_none()
    if not project:
        return {"error": "not found"}

    owner, repo_name = project.full_name.split("/", 1)
    text = f"Project: {project.full_name}\nDescription: {project.description}\nLanguage: {project.language}\nStars: {project.stars}"

    prompt = (
        "Analyze this GitHub trending project. Return a JSON object with:\n"
        '- "tags": list of 3-5 short topic tags (English, lowercase, hyphenated)\n'
        '- "highlights": 2-3 technical highlights (Chinese, concise)\n'
        '- "use_cases": 2-3 potential use cases (Chinese)\n'
        '- "analysis": one-paragraph summary of why this project is trending (Chinese)'
    )

    result = await llm.extract_structured(
        prompt=prompt,
        text=text,
        schema=type("AnalysisResult", (), {
            "__annotations__": {
                "tags": list[str],
                "highlights": list[str],
                "use_cases": list[str],
                "analysis": str,
            }
        }),
    )

    # Update tags
    project.tags = ",".join(result.tags)
    project.is_analyzed = True
    await db.commit()

    # Store to vault
    meta = {
        "标题": f"[Trending] {project.full_name}",
        "阶段": "素材",
        "来源平台": "github-trending",
        "关键词": result.tags,
        "创建时间": project.snapshot_date,
        "关联参考": [f"https://github.com/{project.full_name}"],
        "发布平台": "内部",
        "language": project.language,
        "stars": project.stars,
        "period_stars": project.period_stars,
    }
    body = (
        f"## {project.full_name}\n\n"
        f"{project.description}\n\n"
        f"### 技术亮点\n\n" + "\n".join(f"- {h}" for h in result.highlights) + "\n\n"
        f"### 应用场景\n\n" + "\n".join(f"- {u}" for u in result.use_cases) + "\n\n"
        f"### 趋势分析\n\n{result.analysis}"
    )
    vault.write("素材", f"[Trending] {project.full_name}", meta, body)

    return {
        "id": project.id,
        "tags": result.tags,
        "highlights": result.highlights,
        "use_cases": result.use_cases,
        "analysis": result.analysis,
    }


@router.post("/recommend")
async def recommend_topics(
    interest: str = Query("", description="Your area of interest, e.g. AI编程, 前端开发"),
    db: AsyncSession = Depends(get_db),
):
    """LLM-based topic recommendation from trending projects."""
    from needradar.llm.provider import llm

    stmt = select(TrendingProject).order_by(TrendingProject.period_stars.desc()).limit(30)
    result = await db.execute(stmt)
    projects = result.scalars().all()

    if not projects:
        return {"recommendations": []}

    # Build project summary for LLM
    lines = []
    for p in projects:
        analyzed = f" [tags: {p.tags}]" if p.tags else ""
        lines.append(f"- {p.full_name} ({p.language}, +{p.period_stars} stars): {p.description}{analyzed}")

    project_text = "\n".join(lines)

    prompt = (
        "你是一个技术选题策划师。以下是目前 GitHub 上最热门的项目。"
        f"用户的关注领域是：{interest or '通用'}\n\n"
        "请从这些项目中推荐 5 个最适合用户关注领域的选题方向。\n"
        "每个选题包含：title（标题）、rationale（为什么推荐）、angle（可以写什么角度的内容）、"
        "related_projects（相关项目列表）。\n\n"
        "返回 JSON 对象，字段 recommendations 为数组，每项包含 title/rationale/angle/related_projects。"
    )

    class RecItem:
        __annotations__ = {
            "title": str,
            "rationale": str,
            "angle": str,
            "related_projects": list[str],
        }

    class RecResult:
        __annotations__ = {"recommendations": list[RecItem]}

    rec: RecResult = await llm.extract_structured(
        prompt=prompt,
        text=project_text,
        schema=RecResult,
    )

    return {"recommendations": rec.recommendations}


@router.get("/suggest-keywords")
async def suggest_keywords(
    since: str = Query("weekly"),
    limit: int = Query(12),
    offset: int = Query(-1, description="-1 for random offset"),
    db: AsyncSession = Depends(get_db),
):
    """Extract actionable search keywords from trending projects for task creation."""
    import random

    stmt = (
        select(TrendingProject)
        .where(TrendingProject.since == since)
        .order_by(TrendingProject.period_stars.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    projects = result.scalars().all()

    if offset < 0 and len(projects) > limit:
        offset = random.randint(0, len(projects) - limit)
    elif offset < 0:
        offset = 0
    projects = projects[offset : offset + limit]

    if not projects:
        return {"keywords": [], "projects": []}

    keywords_set: dict[str, int] = {}
    proj_list = []

    for p in projects:
        # Use analyzed tags if available
        if p.tags:
            for tag in p.tags.split(","):
                tag = tag.strip()
                if tag:
                    keywords_set[tag] = keywords_set.get(tag, 0) + p.period_stars

        # Extract short keywords from project name and description
        name_parts = p.full_name.split("/")
        repo_name = name_parts[-1] if len(name_parts) > 1 else p.full_name
        # Convert repo name to readable form: trading-agents → Trading Agents
        readable = repo_name.replace("-", " ").replace("_", " ").title()
        if len(readable) < 40:
            keywords_set[readable] = keywords_set.get(readable, 0) + p.period_stars

        proj_list.append({
            "name": p.full_name,
            "keyword": readable,
            "description": p.description[:80],
            "language": p.language,
            "period_stars": p.period_stars,
        })

    # Sort keywords by cumulative period_stars
    sorted_kw = sorted(keywords_set.items(), key=lambda x: -x[1])[:limit]

    return {
        "keywords": [{"text": kw, "heat": heat} for kw, heat in sorted_kw],
        "projects": proj_list[:limit],
    }
