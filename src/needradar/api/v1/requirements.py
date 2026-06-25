from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from needradar.schemas.schemas import RequirementListResponse, RequirementResponse
from needradar.services.vault_store import vault

router = APIRouter(prefix="/requirements", tags=["requirements"])


@router.get("/by-filename/{filename:path}", response_model=RequirementResponse)
async def get_requirement_by_filename(filename: str):
    """Get a single requirement by its vault filename (relative path from vault root)."""
    try:
        meta, body = vault.read(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Requirement not found: {filename}")

    kw_raw = meta.get("关键词", [])
    if isinstance(kw_raw, list):
        kw_str = ", ".join(str(k) for k in kw_raw) if kw_raw else ""
    else:
        kw_str = str(kw_raw)

    return RequirementResponse(
        title=meta.get("标题", ""),
        description=body[:800],
        source_platform=meta.get("来源平台", ""),
        source_url=meta.get("来源URL", ""),
        sentiment=meta.get("情感倾向", "moderate") or "moderate",
        emotion=meta.get("情绪极性", "neutral") or "neutral",
        confidence=meta.get("置信度", 0.0) or 0.0,
        mention_count=meta.get("提及次数", 1),
        keyword=kw_str,
        stage=meta.get("阶段", "需求"),
        created_at=str(meta.get("创建时间", "")),
    )


@router.get("", response_model=RequirementListResponse)
async def list_requirements(
    keyword: str | None = None,
    platform: str | None = None,
    sentiment: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = vault.search("需求", keyword=keyword or "", platform=platform or "",
                                sentiment=sentiment or "",
                                page=page, page_size=page_size)
    reqs = []
    for item in sorted(items, key=lambda x: x.get("提及次数", 1), reverse=True):
        kw_raw = item.get("关键词", [])
        if isinstance(kw_raw, list):
            kw_str = ", ".join(str(k) for k in kw_raw) if kw_raw else ""
        else:
            kw_str = str(kw_raw)
        reqs.append(RequirementResponse(
            title=item.get("标题", ""),
            description=item.get("_body", "")[:500],
            source_platform=item.get("来源平台", ""),
            source_url=item.get("来源URL", ""),
            sentiment=item.get("情感倾向", "moderate") or "moderate",
            emotion=item.get("情绪极性", "neutral") or "neutral",
            confidence=item.get("置信度", 0.0) or 0.0,
            mention_count=item.get("提及次数", 1),
            keyword=kw_str,
            stage=item.get("阶段", "需求"),
            created_at=str(item.get("创建时间", "")),
            vault_path=str(item.get("_path", "")),
        ))
    return RequirementListResponse(items=reqs, total=total, page=page, page_size=page_size)


# ── Report-derived requirement summary ──

class PainPoint(BaseModel):
    title: str
    severity: str  # 高 / 中到高 / 中 / 低
    description: str
    evidence: str

class InsightSummary(BaseModel):
    report_title: str
    keyword: str
    core_findings: list[str]
    pain_points: list[PainPoint]
    categories: list[dict]  # {name, items}

class RequirementSummaryResponse(BaseModel):
    summaries: list[InsightSummary]
    total_reports: int


@router.get("/summary", response_model=RequirementSummaryResponse)
async def requirement_summary():
    """Extract high-priority requirements from all analysis reports."""
    reports = vault.list_files("初稿")
    summaries = []

    for path, meta, body in reports:
        keyword = ""
        kws = meta.get("关键词", [])
        if isinstance(kws, list) and kws:
            keyword = kws[0] if isinstance(kws[0], str) else str(kws[0])
        elif isinstance(kws, str):
            keyword = kws

        # Split body into lines for simple line-by-line extraction
        lines = body.split("\n")

        findings = _extract_numbered_bold(lines, "核心发现")[:5]
        pain_points = _extract_pain_points(lines)
        categories = _extract_categories(lines)

        summaries.append(InsightSummary(
            report_title=meta.get("标题", path.stem),
            keyword=keyword,
            core_findings=findings,
            pain_points=pain_points,
            categories=categories,
        ))

    return RequirementSummaryResponse(
        summaries=summaries,
        total_reports=len(summaries),
    )


def _extract_numbered_bold(lines: list[str], keyword: str) -> list[str]:
    """Extract numbered bold items from a section header containing keyword."""
    results = []
    in_section = False
    for line in lines:
        if keyword in line and line.strip().startswith("#"):
            in_section = True
            continue
        if in_section and line.strip().startswith("#"):
            break
        if in_section:
            m = re.match(r'\s*\d+\.\s*\*\*(.*?)\*\*', line)
            if m:
                text = re.sub(r'\s+', ' ', m.group(1).strip())[:200]
                results.append(text)
    return results


def _extract_pain_points(lines: list[str]) -> list[PainPoint]:
    """Extract pain points from 痛点 sections — handles multiple report formats."""
    points: list[PainPoint] = []
    current_title = ""
    current_severity = "中"
    current_desc_lines: list[str] = []
    in_point = False

    for line in lines:
        stripped = line.strip()

        # Match: ### 1. 共性痛点：... or ### 痛点 1：... or **共性痛点1：...
        header_m = re.match(
            r'(?:###\s*)?(\d+)[.、]\s*共性痛点[：:]\s*(.*)',
            stripped,
        ) or re.match(
            r'(?:###\s*)?痛点\s*\d+[：:]\s*(.*)',
            stripped,
        ) or re.match(
            r'\*\*共性痛点\d+[：:]\s*(.*?)\*\*',
            stripped,
        )

        if header_m:
            # Flush previous point
            if current_title:
                points.append(_make_pain_point(current_title, current_severity, current_desc_lines))

            # Extract title text
            if len(header_m.groups()) >= 2 and header_m.group(2):
                raw = header_m.group(2).strip()
            else:
                raw = header_m.group(1).strip()

            # Remove trailing severity in parentheses like （严重程度：★★★★★）
            sev_inline = re.search(r'（严重程度[：:](.*?)）', raw)
            if sev_inline:
                current_severity = _normalize_severity(sev_inline.group(1).strip())
                raw = raw[:sev_inline.start()].strip()

            current_title = re.sub(r'\s*[—–]+$', '', raw).strip()
            # Check if we already got severity inline; if not, reset
            if not sev_inline:
                current_severity = "中"
            current_desc_lines = []
            in_point = True
            continue

        if in_point:
            # End of current point: next heading or a new point header
            if stripped.startswith("###") or re.match(r'\d+[.、]\s*共性痛点', stripped) or re.match(r'痛点\s*\d+[：:]', stripped):
                # Flush and check if this is a new point
                if current_title:
                    points.append(_make_pain_point(current_title, current_severity, current_desc_lines))
                current_title = ""
                current_severity = "中"
                current_desc_lines = []
                in_point = False
                # Don't consume this line — re-process as potential header
                continue

            # Extract severity from body: **严重程度：高**
            sev_m = re.search(r'严重程度[：:]\s*(.+?)(?:\*\*|$)', stripped)
            if sev_m:
                current_severity = _normalize_severity(sev_m.group(1).strip().rstrip('**').strip())

            # Collect description lines (skip empty)
            if stripped:
                # Clean leading labels like **表现**： or - **表现**：
                clean = re.sub(r'^-?\s*\*{0,2}(?:表现|影响|根因|具体数据)[：:]\*{0,2}\s*', '', stripped)
                if clean and not clean.startswith('**'):
                    current_desc_lines.append(clean)

    # Flush last point
    if current_title:
        points.append(_make_pain_point(current_title, current_severity, current_desc_lines))

    return points


def _normalize_severity(raw: str) -> str:
    """Normalize severity text to standard levels."""
    if '★' in raw:
        stars = raw.count('★')
        if stars >= 5: return "高"
        if stars >= 4: return "中到高"
        if stars >= 3: return "中"
        return "低"
    raw = raw.strip()
    if '高' in raw and '中' not in raw: return "高"
    if '中' in raw and '高' in raw: return "中到高"
    if '高' in raw: return "高"
    if '中' in raw: return "中"
    return raw or "中"


def _make_pain_point(title: str, severity: str, desc_lines: list[str]) -> PainPoint:
    desc = " ".join(desc_lines)[:300]
    return PainPoint(title=title, severity=severity, description=desc, evidence=desc[:200])


def _extract_categories(lines: list[str]) -> list[dict]:
    """Extract requirement categories from 类别 sections."""
    categories: list[dict] = []
    current_name = ""
    current_items: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Match: ### 类别1：... or ### 类别 1：... (with optional space)
        m = re.match(r'###\s*类别\s*\d+[：:]\s*(.*)', stripped)
        if m:
            if current_name:
                categories.append({"name": current_name, "items": current_items[:5]})
            current_name = m.group(1).strip()
            current_items = []
            continue

        if current_name:
            # From bold items: **Item Name**
            bold_m = re.search(r'\*\*(.*?)\*\*', stripped)
            if bold_m:
                item = bold_m.group(1).strip().rstrip('：:')
                if item and len(item) < 80 and item not in ('代表性需求', '代表性需求：'):
                    current_items.append(item)
            # From table rows: | item | description |
            elif stripped.startswith('|') and not stripped.startswith('|#') and not stripped.startswith('| -'):
                cells = [c.strip() for c in stripped.split('|')[1:-1]]
                if cells:
                    item = cells[0].strip()
                    # Skip header rows and empty items
                    if item and item not in ('需求', '代表性原文') and not item.startswith('---') and len(item) < 80:
                        current_items.append(item)

    if current_name:
        categories.append({"name": current_name, "items": current_items[:5]})

    return categories
