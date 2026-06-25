"""create student_reviews table

Revision ID: 20260619_student_reviews
Revises: 20260618_viewing_codes
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

revision = "20260619_student_reviews"
down_revision = "20260618_viewing_codes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "student_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("landlord_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("viewing_id", sa.Integer(), sa.ForeignKey("viewing_requests.id"), nullable=True),
        sa.Column("landlord_name", sa.String(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_student_reviews_student_id", "student_reviews", ["student_id"])
    op.create_index("ix_student_reviews_landlord_id", "student_reviews", ["landlord_id"])
    op.create_index("ix_student_reviews_viewing_id", "student_reviews", ["viewing_id"])
    op.create_index("ix_student_reviews_status", "student_reviews", ["status"])


def downgrade():
    op.drop_table("student_reviews")
