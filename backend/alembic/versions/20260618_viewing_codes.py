"""add viewing code and completion tracking

Revision ID: 20260618_viewing_codes
Revises: 20260618_user_sessions
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "20260618_viewing_codes"
down_revision = "20260618_user_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("viewing_requests", sa.Column("viewing_code", sa.String(), nullable=True))
    op.add_column("viewing_requests", sa.Column("code_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("viewing_requests", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_viewing_requests_viewing_code", "viewing_requests", ["viewing_code"], unique=True)


def downgrade():
    op.drop_index("ix_viewing_requests_viewing_code", table_name="viewing_requests")
    op.drop_column("viewing_requests", "completed_at")
    op.drop_column("viewing_requests", "code_verified")
    op.drop_column("viewing_requests", "viewing_code")
