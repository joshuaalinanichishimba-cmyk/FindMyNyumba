"""add user_sessions table for session management / token revocation

Revision ID: 20260618_user_sessions
Revises: 20260617_add_image_hash
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "20260618_user_sessions"
down_revision = "20260617_add_image_hash"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("user_sessions")
