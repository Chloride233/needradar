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
    from needradar.core.database import async_session_factory, engine
    from needradar.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from needradar.models.crawl_task import CrawlTask, TaskStatus
    from needradar.models.pipeline_run import PipelineRun
    from needradar.services.analysis_service import AnalysisService
    import datetime
    import json

    logger.info(f"[1/4] Starting pipeline: keyword={keyword} platforms={platforms}")

    async with async_session_factory() as db:
        run = PipelineRun(keyword=keyword, status="running", stages_json="[]")
        db.add(run)
        await db.flush()

        def _stage(name: str, status: str) -> dict:
            return {"name": name, "status": status, "platforms": platforms,
                    "started_at": str(datetime.datetime.now(datetime.timezone.utc))}

        def _save_stages(stages: list[dict]):
            run.stages_json = json.dumps(stages, ensure_ascii=False)

        stages: list[dict] = []

        # Stage 1: Crawl + Extract
        stages.append(_stage("crawling", "running"))
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        await db.flush()

        tasks = [CrawlTask(keyword=keyword, platform=p, status=TaskStatus.PENDING) for p in platforms]
        for t in tasks:
            db.add(t)
        await db.flush()
        svc = AnalysisService(db)
        completed = await svc.run_pipeline(keyword, platforms, existing_task_ids=[t.id for t in tasks])

        stages[-1]["status"] = "completed"
        stages[-1]["completed_at"] = str(datetime.datetime.now(datetime.timezone.utc))
        stages[-1]["task_count"] = len(completed)
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        await db.flush()
        noise_total = sum(t.noise_count for t in completed)
        extracted_total = sum(t.extracted_count for t in completed)
        logger.info(f"[1/4] Crawl done: {len(completed)} tasks, {noise_total} noise filtered, {extracted_total} extracted")

        # Stage 2: Report
        stages.append(_stage("reporting", "running"))
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        await db.flush()
        logger.info("[2/4] Generating report...")

        from needradar.services.report_service import get_report_service
        rs = get_report_service()
        report_path = await rs.generate_report(keyword)
        logger.info(f"[2/4] Report: {report_path}")
        stages[-1]["status"] = "completed"
        stages[-1]["path"] = str(report_path)
        stages[-1]["completed_at"] = str(datetime.datetime.now(datetime.timezone.utc))
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        await db.flush()

        # Stage 3: Verify
        stages.append(_stage("verifying", "running"))
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        await db.flush()
        logger.info("[3/4] Verifying...")

        from needradar.services.content_verifier import get_verifier
        verifier = get_verifier()
        v_output = await verifier.verify_report(report_path.stem)
        logger.info(f"[3/4] Score={v_output.overall_score} hallucinations={v_output.hallucination_count}")
        stages[-1]["status"] = "completed"
        stages[-1]["score"] = v_output.overall_score
        stages[-1]["completed_at"] = str(datetime.datetime.now(datetime.timezone.utc))
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        await db.flush()

        # Stage 4: Score opportunities
        stages.append(_stage("scoring", "running"))
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        await db.flush()
        logger.info("[4/4] Scoring opportunities...")
        try:
            from needradar.services.opportunity_scorer import OpportunityScorer
            scorer = OpportunityScorer(db)
            opps = await scorer.score_keyword(keyword)
            logger.info(f"[4/4] {len(opps)} opportunities scored")
            stages[-1]["status"] = "completed"
            stages[-1]["opportunities_count"] = len(opps)
        except Exception as e:
            logger.warning(f"Scoring failed: {e}")
            stages[-1]["status"] = "failed"
            stages[-1]["error"] = str(e)
        stages[-1]["completed_at"] = str(datetime.datetime.now(datetime.timezone.utc))

        run.status = "completed"
        run.stages_json = json.dumps(stages, ensure_ascii=False)
        run.task_ids_json = json.dumps([t.id for t in completed], ensure_ascii=False)
        await db.flush()

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
