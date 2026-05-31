"""NeedRadar CLI — one-command pipeline execution.

Usage:
    python -m needradar.cli run <keyword> [--platforms github,stackoverflow]
    python -m needradar.cli report <keyword>
    python -m needradar.cli status
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="<level>{message}</level>")


async def _run_pipeline(keyword: str, platforms: list[str]) -> None:
    # Ensure tables exist
    from needradar.core.database import async_session_factory, engine
    from needradar.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from needradar.models.crawl_task import CrawlTask, TaskStatus
    from needradar.services.analysis_service import AnalysisService

    logger.info(f"Starting pipeline: keyword={keyword}, platforms={platforms}")

    async with async_session_factory() as db:
        tasks = []
        for platform in platforms:
            task = CrawlTask(keyword=keyword, platform=platform, status=TaskStatus.PENDING)
            db.add(task)
            tasks.append(task)
        await db.flush()

        service = AnalysisService(db)
        await service.run_pipeline(keyword, platforms, existing_task_ids=[t.id for t in tasks])

        # Auto-generate report
        from needradar.services.report_service import get_report_service
        rs = get_report_service()
        report_path = await rs.generate_report(keyword)
        logger.info(f"Report generated: {report_path}")

        # Auto-verify
        from needradar.services.content_verifier import get_verifier
        report_title = report_path.stem
        verifier = get_verifier()
        v_output = await verifier.verify_report(report_title)
        logger.info(
            f"Verification: score={v_output.overall_score}, "
            f"hallucinations={v_output.hallucination_count}, "
            f"flagged={v_output.flagged_count}"
        )

        await db.commit()

    logger.info("Pipeline complete!")


async def _generate_report(keyword: str) -> None:
    from needradar.services.report_service import get_report_service
    rs = get_report_service()
    report_path = await rs.generate_report(keyword)
    logger.info(f"Report generated: {report_path}")

    from needradar.services.content_verifier import get_verifier
    verifier = get_verifier()
    v_output = await verifier.verify_report(report_path.stem)
    logger.info(
        f"Verification: score={v_output.overall_score}, "
        f"hallucinations={v_output.hallucination_count}"
    )


async def _show_status() -> None:
    from needradar.services.vault_store import vault

    stages = {"素材", "需求", "大纲", "初稿", "终稿", "已归档"}
    print("NeedRadar Status")
    print("=" * 40)
    total = 0
    for stage in stages:
        files = vault.list_files(stage)
        count = len(files)
        total += count
        if count > 0:
            print(f"  {stage}: {count} files")
    print(f"  Total: {total} files")
    print()

    # Show latest tasks
    from sqlalchemy import select

    from needradar.core.database import async_session_factory
    from needradar.models.crawl_task import CrawlTask

    async with async_session_factory() as db:
        stmt = select(CrawlTask).order_by(CrawlTask.created_at.desc()).limit(10)
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        if tasks:
            print("Recent Tasks:")
            for t in tasks:
                print(f"  [{t.status.value}] {t.keyword} @ {t.platform} — {t.total_items} items")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="needradar",
        description="NeedRadar — AI-driven requirement mining engine",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # run: one-command pipeline
    run_parser = sub.add_parser("run", help="Run full pipeline: crawl → extract → report → verify")
    run_parser.add_argument("keyword", help="Search keyword")
    run_parser.add_argument(
        "--platforms", default="github,stackoverflow,juejin",
        help="Comma-separated platforms (default: github,stackoverflow,juejin)",
    )

    # report: generate report from existing data
    report_parser = sub.add_parser("report", help="Generate report from existing requirements")
    report_parser.add_argument("keyword", help="Report keyword")

    # status: show current state
    sub.add_parser("status", help="Show vault status and recent tasks")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if args.command == "run":
        platforms = [p.strip() for p in args.platforms.split(",")]
        asyncio.run(_run_pipeline(args.keyword, platforms))
    elif args.command == "report":
        asyncio.run(_generate_report(args.keyword))
    elif args.command == "status":
        asyncio.run(_show_status())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
