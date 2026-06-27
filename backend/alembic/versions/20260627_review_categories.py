"""add structured rating categories to reviews

Revision ID: 20260627_review_categories
Revises: 20260620_review_reply
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260627_review_categories"
down_revision = "20260620_review_reply"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reviews", sa.Column("rating_accuracy", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("rating_landlord", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("rating_value", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("reviews", "rating_value")
    op.drop_column("reviews", "rating_landlord")
    op.drop_column("reviews", "rating_accuracy")
