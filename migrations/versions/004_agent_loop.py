"""add agent loop tables and missing columns

Revision ID: 004
Revises: 003
Create Date: 2026-06-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "pipeline_runs" not in existing_tables:
        op.create_table(
            "pipeline_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("keyword", sa.String(200), nullable=False, index=True),
            sa.Column("status", sa.String(30), server_default="pending"),
            sa.Column("stages_json", sa.Text(), server_default="[]"),
            sa.Column("task_ids_json", sa.Text(), server_default="[]"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("current_phase", sa.String(30), nullable=True),
            sa.Column("gate_status", sa.String(20), server_default="none"),
            sa.Column("is_agent_mode", sa.Boolean(), server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        existing_tables.append("pipeline_runs")

    # ── crawl_tasks: add missing columns ──
    _add_column_if_missing("crawl_tasks", "new_items", sa.Integer(), server_default="0")
    _add_column_if_missing("crawl_tasks", "skipped_items", sa.Integer(), server_default="0")
    _add_column_if_missing("crawl_tasks", "noise_count", sa.Integer(), server_default="0")
    _add_column_if_missing("crawl_tasks", "extracted_count", sa.Integer(), server_default="0")
    _add_column_if_missing("crawl_tasks", "filter_mode", sa.String(20), server_default="off")
    _add_column_if_missing("crawl_tasks", "report_path", sa.String(500), nullable=True)

    # ── pipeline_runs: add agent mode columns ──
    _add_column_if_missing("pipeline_runs", "current_phase", sa.String(30), nullable=True)
    _add_column_if_missing("pipeline_runs", "gate_status", sa.String(20), server_default="none")
    _add_column_if_missing("pipeline_runs", "is_agent_mode", sa.Boolean(), server_default=sa.text("0"))

    # ── verification_results: add verdict_override ──
    _add_column_if_missing("verification_results", "verdict_override", sa.String(50), nullable=True)

    # ── New tables (idempotent) ──

    if "pipeline_phases" not in existing_tables:
        op.create_table(
            "pipeline_phases",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id"), index=True),
            sa.Column("phase", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("started_at", sa.String(40), nullable=True),
            sa.Column("completed_at", sa.String(40), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "quality_gates" not in existing_tables:
        op.create_table(
            "quality_gates",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id"), index=True),
            sa.Column("gate_type", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("items_json", sa.Text(), nullable=True),
            sa.Column("items_count", sa.Integer(), server_default="0"),
            sa.Column("human_decision", sa.String(20), nullable=True),
            sa.Column("human_edits_json", sa.Text(), nullable=True),
            sa.Column("reviewer_note", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.String(40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "feedback_records" not in existing_tables:
        op.create_table(
            "feedback_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id"), index=True),
            sa.Column("gate_id", sa.Integer(), sa.ForeignKey("quality_gates.id"), index=True),
            sa.Column("feedback_type", sa.String(30), nullable=False),
            sa.Column("entity_type", sa.String(30), nullable=False),
            sa.Column("entity_id", sa.String(500), nullable=False),
            sa.Column("before_json", sa.Text(), nullable=True),
            sa.Column("after_json", sa.Text(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "knowledge_entries" not in existing_tables:
        op.create_table(
            "knowledge_entries",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("category", sa.String(30), nullable=False, index=True),
            sa.Column("key", sa.String(200), nullable=False, index=True),
            sa.Column("value_json", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), server_default="0.5"),
            sa.Column("source_count", sa.Integer(), server_default="1"),
            sa.Column("last_confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("category", "key", name="uq_knowledge_cat_key"),
        )


def downgrade() -> None:
    op.drop_table("knowledge_entries")
    op.drop_table("feedback_records")
    op.drop_table("quality_gates")
    op.drop_table("pipeline_phases")

    op.drop_column("verification_results", "verdict_override")
    op.drop_column("pipeline_runs", "is_agent_mode")
    op.drop_column("pipeline_runs", "gate_status")
    op.drop_column("pipeline_runs", "current_phase")

    op.drop_column("crawl_tasks", "report_path")
    op.drop_column("crawl_tasks", "filter_mode")
    op.drop_column("crawl_tasks", "extracted_count")
    op.drop_column("crawl_tasks", "noise_count")
    op.drop_column("crawl_tasks", "skipped_items")
    op.drop_column("crawl_tasks", "new_items")


def _add_column_if_missing(table: str, column: str, col_type, **kwargs):
    """Add a column only if it doesn't already exist (idempotent)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns(table)}
    if column not in existing_cols:
        op.add_column(table, sa.Column(column, col_type, **kwargs))
