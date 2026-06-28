"""add search_logs table for anonymous search analytics

Revision ID: 20260628_search_logs
Revises: 20260627_review_categories
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "20260628_search_logs"
down_revision = "20260627_review_categories"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "search_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("query", sa.String(), nullable=True),
        sa.Column("university", sa.String(), nullable=True),
        sa.Column("min_price", sa.Float(), nullable=True),
        sa.Column("max_price", sa.Float(), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_search_logs_query", "search_logs", ["query"])
    op.create_index("ix_search_logs_university", "search_logs", ["university"])
    op.create_index("ix_search_logs_created_at", "search_logs", ["created_at"])


def downgrade():
    op.drop_table("search_logs")
