from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.schemas.schemas import ReportListResponse, ReportResponse
from needradar.services.report_service import get_report_service
from needradar.services.vault_store import vault

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=201)
async def generate_report(
    keyword: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    service = get_report_service()
    filepath = await service.generate_report(keyword)
    meta, body = vault.read(filepath)

    await _link_references(db, meta.get("标题", ""), meta)

    return ReportResponse(
        title=meta.get("标题", ""),
        keyword=keyword,
        content=body,
        stage=meta.get("阶段", "初稿"),
        created_at=meta.get("创建时间", ""),
    )


async def _link_references(db: AsyncSession, report_title: str, meta: dict) -> None:
    """Create EntityLink rows: report --[references]--> requirements."""
    try:
        from needradar.models.link import LinkType
        from needradar.schemas.schemas import EntityLinkCreateRequest
        from needradar.services.link_service import EntityLinkService

        related = meta.get("关联需求", [])
        if isinstance(related, str):
            related = [related]
        if not related:
            return

        svc = EntityLinkService(db)
        refs = []
        for ref in related:
            import re
            m = re.search(r'\[\[.*?\|(.*?)\]\]', ref)
            need_title = m.group(1) if m else ref.strip('[]')
            refs.append(EntityLinkCreateRequest(
                source_type="report", source_id=report_title,
                link_type=LinkType.REFERENCES, target_type="requirement", target_id=need_title,
            ))
        if refs:
            await svc.batch_create(refs)
    except Exception as e:
        from loguru import logger
        logger.warning("entity_link_failed", link_type="references", error=str(e))


@router.get("", response_model=ReportListResponse)
async def list_reports(
    stage: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stages = [stage] if stage else ["初稿", "终稿", "已归档"]
    all_reports = []
    for s in stages:
        all_reports.extend(vault.list_files(s))
    total = len(all_reports)
    start = (page - 1) * page_size
    paged = all_reports[start:start + page_size]
    items = []
    for path, meta, body in paged:
        kws = meta.get("关键词", [])
        kw = kws[0] if isinstance(kws, list) and kws else str(kws)
        items.append(ReportResponse(
            title=meta.get("标题", ""),
            keyword=kw,
            content="",
            stage=meta.get("阶段", ""),
            created_at=str(meta.get("创建时间", "")),
        ))
    return ReportListResponse(items=items, total=total)


@router.get("/download/{title}")
async def download_report(title: str):
    for stage_dir in ["初稿", "终稿", "已归档"]:
        path = vault._dir(stage_dir) / f"{title}.md"
        if path.exists():
            _, body = vault.read(path)
            filename = f"needradar-{title}.md"
            encoded = quote(filename)
            return PlainTextResponse(
                content=body,
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
            )
    raise HTTPException(status_code=404, detail="Report not found")


@router.get("/by-filename/{filename}")
async def get_report_by_filename(filename: str):
    """Read a report by its vault filename (used by auto-generated task reports)."""
    for stage_dir in ["初稿", "终稿", "已归档"]:
        path = vault._dir(stage_dir) / filename
        if path.exists():
            meta, body = vault.read(path)
            kws = meta.get("关键词", [])
            kw = kws[0] if isinstance(kws, list) and kws else str(kws)
            return ReportResponse(
                title=meta.get("标题", ""),
                keyword=kw,
                content=body,
                stage=meta.get("阶段", ""),
                created_at=str(meta.get("创建时间", "")),
            )
    raise HTTPException(status_code=404, detail="Report not found")
