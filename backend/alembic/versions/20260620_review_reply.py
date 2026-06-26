"""add reply columns to reviews

Revision ID: 20260620_review_reply
Revises: 20260619_student_reviews
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "20260620_review_reply"
down_revision = "20260619_student_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reviews", sa.Column("reply_text", sa.Text(), nullable=True))
    op.add_column("reviews", sa.Column("reply_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("reviews", "reply_at")
    op.drop_column("reviews", "reply_text")
