"""complete current ORM schema

Revision ID: 005
Revises: 004
Create Date: 2026-06-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not _table_exists("crawl_fingerprints"):
        op.create_table(
            "crawl_fingerprints",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("keyword", sa.String(200), nullable=False),
            sa.Column("platform", sa.String(50), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=True),
        )
    _create_index_if_missing("ix_crawl_fingerprints_keyword", "crawl_fingerprints", ["keyword"])
    _create_index_if_missing("ix_fp_keyword_platform", "crawl_fingerprints", ["keyword", "platform"])

    if not _table_exists("entity_links"):
        op.create_table(
            "entity_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_type", sa.String(50), nullable=False),
            sa.Column("source_id", sa.String(500), nullable=False),
            sa.Column("link_type", sa.String(50), nullable=False),
            sa.Column("target_type", sa.String(50), nullable=False),
            sa.Column("target_id", sa.String(500), nullable=False),
            sa.Column("metadata_json", sa.Text(), server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    _create_index_if_missing("ix_entity_links_source_type", "entity_links", ["source_type"])
    _create_index_if_missing("ix_entity_links_source_id", "entity_links", ["source_id"])
    _create_index_if_missing("ix_entity_links_link_type", "entity_links", ["link_type"])
    _create_index_if_missing("ix_entity_links_target_type", "entity_links", ["target_type"])
    _create_index_if_missing("ix_entity_links_target_id", "entity_links", ["target_id"])

    if not _table_exists("project_opportunities"):
        op.create_table(
            "project_opportunities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("keyword", sa.String(200), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("description", sa.Text(), server_default=""),
            sa.Column("scores_json", sa.Text(), server_default="{}"),
            sa.Column("traction_json", sa.Text(), server_default="{}"),
            sa.Column("source_req_ids_json", sa.Text(), server_default="[]"),
            sa.Column("status", sa.String(30), server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    _create_index_if_missing("ix_project_opportunities_keyword", "project_opportunities", ["keyword"])

    if not _table_exists("project_proposals"):
        op.create_table(
            "project_proposals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("project_opportunities.id"), nullable=True),
            sa.Column("keyword", sa.String(200), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("problem_statement", sa.Text(), server_default=""),
            sa.Column("target_user", sa.Text(), server_default=""),
            sa.Column("mvp_scope_json", sa.Text(), server_default="[]"),
            sa.Column("suggested_stack_json", sa.Text(), server_default="{}"),
            sa.Column("effort_estimate_hours", sa.Integer(), server_default="0"),
            sa.Column("effort_breakdown_json", sa.Text(), server_default="{}"),
            sa.Column("traction_signals_json", sa.Text(), server_default="[]"),
            sa.Column("claude_prompt", sa.Text(), server_default=""),
            sa.Column("risks_json", sa.Text(), server_default="[]"),
            sa.Column("status", sa.String(30), server_default="draft"),
            sa.Column("vault_path", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    _create_index_if_missing("ix_project_proposals_keyword", "project_proposals", ["keyword"])

    if not _table_exists("scheduled_jobs"):
        op.create_table(
            "scheduled_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("keyword", sa.String(200), nullable=False),
            sa.Column("platforms", sa.Text(), nullable=False),
            sa.Column("interval_minutes", sa.Integer(), server_default="60"),
            sa.Column("status", sa.Enum("ACTIVE", "PAUSED", name="jobstatus"), server_default="ACTIVE"),
            sa.Column("last_run_at", sa.Text(), nullable=True),
            sa.Column("last_task_ids", sa.Text(), nullable=True),
            sa.Column("run_count", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    _create_index_if_missing("ix_scheduled_jobs_keyword", "scheduled_jobs", ["keyword"])
    _create_index_if_missing("ix_scheduled_jobs_status", "scheduled_jobs", ["status"])

    if not _table_exists("trending_projects"):
        op.create_table(
            "trending_projects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("full_name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), server_default=""),
            sa.Column("language", sa.String(50), server_default=""),
            sa.Column("stars", sa.Integer(), server_default="0"),
            sa.Column("forks", sa.Integer(), server_default="0"),
            sa.Column("period_stars", sa.Integer(), server_default="0"),
            sa.Column("since", sa.String(20), nullable=False),
            sa.Column("contributors", sa.Text(), server_default=""),
            sa.Column("tags", sa.Text(), server_default=""),
            sa.Column("snapshot_date", sa.String(20), nullable=False),
            sa.Column("is_analyzed", sa.Boolean(), server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    _create_index_if_missing("ix_trending_projects_full_name", "trending_projects", ["full_name"])
    _create_index_if_missing("ix_trending_projects_language", "trending_projects", ["language"])
    _create_index_if_missing("ix_trending_projects_since", "trending_projects", ["since"])
    _create_index_if_missing("ix_trending_projects_snapshot_date", "trending_projects", ["snapshot_date"])

    if not _table_exists("verification_results"):
        op.create_table(
            "verification_results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("report_title", sa.String(200), nullable=False),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("fact_check_score", sa.Float(), nullable=True),
            sa.Column("consistency_score", sa.Float(), nullable=True),
            sa.Column("source_reliability_score", sa.Float(), nullable=True),
            sa.Column("total_claims", sa.Integer(), server_default="0"),
            sa.Column("hallucination_count", sa.Integer(), server_default="0"),
            sa.Column("flagged_count", sa.Integer(), server_default="0"),
            sa.Column("claims_json", sa.Text(), nullable=True),
            sa.Column("suggestions_json", sa.Text(), nullable=True),
            sa.Column("reviewer_note", sa.Text(), nullable=True),
            sa.Column("verdict_override", sa.String(50), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    _create_index_if_missing("ix_verification_results_report_title", "verification_results", ["report_title"])


def downgrade() -> None:
    op.drop_table("verification_results")
    op.drop_table("trending_projects")
    op.drop_table("scheduled_jobs")
    op.drop_table("project_proposals")
    op.drop_table("project_opportunities")
    op.drop_table("entity_links")
    op.drop_table("crawl_fingerprints")


def _table_exists(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if not _table_exists(table):
        return
    indexes = sa.inspect(op.get_bind()).get_indexes(table)
    if name not in {idx["name"] for idx in indexes}:
        op.create_index(name, table, columns)
