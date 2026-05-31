from __future__ import annotations

import datetime
import re
from pathlib import Path

import yaml
from loguru import logger

from needradar.llm.provider import llm
from needradar.services.vault_store import vault
from needradar.vector import create_vector_store

_prompts_cache: dict | None = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is None:
        path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts.yaml"
        with open(path, encoding="utf-8") as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


class ReportService:

    def __init__(self) -> None:
        self._vs = create_vector_store()

    async def generate_report(self, keyword: str) -> Path:
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        title = f"需求洞察报告 — {keyword}"

        # Step 1: Vector retrieval (RAG)
        try:
            retrieval_context = await self._retrieve(keyword)
        except Exception as e:
            logger.warning("vector_retrieval_failed_fallback", keyword=keyword, error=str(e))
            retrieval_context = self._retrieve_fallback(keyword)

        # Step 2: LLM analysis based on retrieved context
        ai_analysis = await self._analyze(keyword, retrieval_context)

        # Step 3: Statistical summary from retrieval results
        stats_section = self._build_stats_from_retrieval(retrieval_context)

        # Step 4: Combine and write to Obsidian vault
        meta = self._frontmatter(title, keyword, now_str, retrieval_context["top_titles"])
        body = f"# {title}\n"
        body += f"> 生成时间: {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M}\n\n"
        body += ai_analysis
        body += "\n\n---\n\n## 附录：数据统计\n\n"
        body += stats_section

        report_path = vault.write("初稿", title, meta, body)

        # Step 5: Update backlinks on referenced needs
        self._update_backlinks(title, retrieval_context["top_titles"])

        # Step 6: Generate relationship graph
        self._write_relationship_graph(keyword)

        return report_path

    async def _retrieve(self, keyword: str) -> dict:
        results = await self._vs.query([keyword], n_results=20)
        if not results:
            return {"documents": [], "top_titles": []}

        documents = []
        top_titles = []
        for r in results:
            if r.document:
                documents.append(r.document)
            top_titles.append(f"[[02-需求池/{r.id}|{r.id}]]")

        return {"documents": documents, "top_titles": top_titles, "results": results}

    @staticmethod
    def _sanitize_wikilink_title(title: str) -> str:
        """Remove characters that break wikilink syntax."""
        return title.replace("|", "-").replace("[", "(").replace("]", ")")

    def _retrieve_fallback(self, keyword: str) -> dict:
        """Fallback: search vault directly when vector retrieval fails."""
        needs, _ = vault.search("需求", keyword=keyword, page_size=50)
        documents = [n.get("_body", "") for n in needs if n.get("_body")]
        top_titles = []
        for n in needs:
            raw_title = n.get("标题") or n.get("_path", "")
            safe_title = self._sanitize_wikilink_title(raw_title)
            top_titles.append(f"[[02-需求池/{safe_title}|{safe_title}]]")
        return {"documents": documents, "top_titles": top_titles, "results": []}

    async def _analyze(self, keyword: str, context: dict) -> str:
        documents = context.get("documents", [])
        if not documents:
            return "> 未检索到相关需求数据，无法生成 AI 分析。\n"

        context_text = "\n---\n".join(documents[:15])

        prompts = _load_prompts()
        analysis_prompt = prompts.get("report_analysis", "")

        try:
            analysis = await llm.complete([
                {"role": "system", "content": analysis_prompt},
                {
                    "role": "user",
                    "content": f"以下是检索到的相关需求数据：\n\n{context_text}",
                },
                {
                    "role": "user",
                    "content": f"分析关键词：{keyword}",
                },
            ])
            # Normalize literal \n from LLM output to actual newlines
            return analysis.replace('\\n', '\n')
        except Exception as e:
            logger.error("rag_analysis_failed", error=str(e))
            return f"> AI 分析生成失败: {str(e)}\n"

    def _build_stats_from_retrieval(self, context: dict) -> str:
        results = context.get("results", [])
        if not results:
            return "- 检索到相关需求: **0**\n"

        total = len(results)
        platform_dist: dict[str, int] = {}
        sentiment_dist: dict[str, int] = {}
        emotion_dist: dict[str, int] = {}
        req_details: list[dict] = []
        for r in results:
            existing = vault.find_by_title("需求", r.id)
            if existing:
                meta, _ = vault.read(existing)
                p = meta.get("来源平台", "unknown")
                s = meta.get("情感倾向") or "moderate"
                e = meta.get("情绪极性") or "neutral"
                mentions = meta.get("提及次数", 1)
            else:
                p = r.metadata.get("platform", "unknown") if r.metadata else "unknown"
                s = r.metadata.get("sentiment", "moderate") if r.metadata else "moderate"
                e = r.metadata.get("emotion", "neutral") if r.metadata else "neutral"
                mentions = int(r.metadata.get("mentions", 1)) if r.metadata else 1
            platform_dist[p] = platform_dist.get(p, 0) + 1
            sentiment_dist[s] = sentiment_dist.get(s, 0) + 1
            emotion_dist[e] = emotion_dist.get(e, 0) + 1
            req_details.append({"标题": r.id, "来源平台": p, "情感倾向": s, "情绪极性": e, "提及次数": mentions})

        strong_pct = round(sentiment_dist.get("strong", 0) / total * 100, 1)
        neg_pct = round(emotion_dist.get("negative", 0) / total * 100, 1)

        lines = [
            f"- 检索到相关需求: **{total}**",
            f"- 数据源: {', '.join(platform_dist.keys())}",
            f"- 强烈需求占比: **{strong_pct}%**",
            f"- 负面情绪占比: **{neg_pct}%**",
            "",
            "### 平台分布",
            "| 平台 | 需求数 | 占比 |",
            "|------|--------|------|",
        ]
        for platform, count in sorted(platform_dist.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1)
            lines.append(f"| {platform} | {count} | {pct}% |")

        lines += [
            "",
            "### 情感强度分布",
            "| 强烈程度 | 数量 | 占比 |",
            "|---------|------|------|",
        ]
        for sentiment, count in sorted(sentiment_dist.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1)
            lines.append(f"| {sentiment} | {count} | {pct}% |")

        emotion_labels = {"positive": "正面", "negative": "负面", "neutral": "中性"}
        lines += [
            "",
            "### 情绪极性分布",
            "| 情绪 | 数量 | 占比 |",
            "|------|------|------|",
        ]
        for emotion, count in sorted(emotion_dist.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1)
            label = emotion_labels.get(emotion, emotion)
            lines.append(f"| {label} | {count} | {pct}% |")

        lines += ["", "### 相关需求列表"]
        top_reqs = sorted(req_details, key=lambda r: r["提及次数"], reverse=True)[:10]
        for i, req in enumerate(top_reqs, 1):
            rt = req["标题"]
            lines.append(
                f"{i}. [[02-需求池/{rt}|{rt}]] "
                f"({req['来源平台']} · {req['情感倾向']} · {emotion_labels.get(req['情绪极性'], '中性')} · 提及{req['提及次数']}次)"
            )

        return "\n".join(lines)

    def _update_backlinks(self, report_title: str, need_refs: list[str]) -> None:
        """Add backlink to report in each referenced need's frontmatter."""
        for ref in need_refs:
            m = re.search(r'\[\[.*?/(.*?)\|', ref)
            need_title = m.group(1) if m else ref.strip('[]|')
            need_path = vault.find_by_title("需求", need_title)
            if not need_path:
                continue
            meta, body = vault.read(need_path)
            reports = meta.get("关联报告", [])
            report_link = f"[[03-分析车间/初稿打磨/{report_title}|{report_title}]]"
            if report_link not in reports:
                reports.append(report_link)
                vault.update_frontmatter(need_path, {"关联报告": reports})

    def _write_relationship_graph(self, keyword: str) -> None:
        """Generate a Mermaid relationship graph for the keyword's needs."""
        needs = vault.list_files("需求")
        related: list[tuple[str, str, str, str]] = []  # (title, platform, sentiment, keyword)
        for _path, meta, _body in needs:
            kws = meta.get("关键词", [])
            if isinstance(kws, list) and keyword in [str(k) for k in kws]:
                related.append((
                    meta.get("标题", "unknown"),
                    meta.get("来源平台", "unknown"),
                    meta.get("情感倾向", "moderate"),
                    meta.get("情绪极性", "neutral"),
                ))
        if not related:
            return

        # Mermaid graph
        lines = ["graph TD"]
        lines.append(f'    R["📋 {keyword}<br/>洞察报告"]')

        # Group by platform
        platforms: dict[str, list[tuple[str, str, str]]] = {}
        for title, platform, sentiment, emotion in related:
            platforms.setdefault(platform, []).append((title, sentiment, emotion))

        sentiment_colors = {"strong": "#ef4444", "moderate": "#f59e0b", "mild": "#94a3b8"}
        emotion_icons = {"positive": "😊", "negative": "😟", "neutral": "😐"}

        for platform, needs_list in platforms.items():
            safe_plat = platform.replace(" ", "_")
            lines.append(f'    P_{safe_plat}["{platform}"]')
            lines.append(f'    R --> P_{safe_plat}')
            for i, (title, sentiment, emotion) in enumerate(needs_list[:8]):
                node_id = f"N_{safe_plat}_{i}"
                short = title[:25] + ("..." if len(title) > 25 else "")
                icon = emotion_icons.get(emotion, "")
                color = sentiment_colors.get(sentiment, "#94a3b8")
                lines.append(f'    {node_id}("{icon} {short}")')
                lines.append(f'    P_{safe_plat} --> {node_id}')
                lines.append(f'    style {node_id} fill:{color}22,stroke:{color}')

        graph_body = "\n".join(lines)
        graph_meta = {
            "标题": f"关系图谱 — {keyword}",
            "阶段": "初稿",
            "关键词": [keyword],
            "创建时间": str(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")),
        }
        vault.write("图谱", f"关系图谱 — {keyword}", graph_meta, f"```mermaid\n{graph_body}\n```")

    def _frontmatter(self, title: str, keyword: str, date_str: str,
                     refs: list[str] | None = None) -> dict:
        return {
            "标题": title,
            "阶段": "初稿",
            "关键词": [keyword],
            "创建时间": date_str,
            "关联需求": refs or [],
            "关联参考": [],
            "发布平台": "内部",
        }


_report_service = None


def get_report_service() -> ReportService:
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
