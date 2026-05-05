"""add cached_tokens to llm_usage

Revision ID: 003
Revises: 002
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_usage", sa.Column("cached_tokens", sa.Integer(), server_default="0"))


def downgrade() -> None:
    op.drop_column("llm_usage", "cached_tokens")
