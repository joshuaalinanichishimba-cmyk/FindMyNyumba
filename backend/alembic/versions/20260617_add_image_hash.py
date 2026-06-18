"""add image_hash to listing_media for duplicate detection

Revision ID: 20260617_add_image_hash
Revises: 20260601_listing_media
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260617_add_image_hash"
down_revision = "20260601_listing_media"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "listing_media",
        sa.Column("image_hash", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_listing_media_image_hash",
        "listing_media",
        ["image_hash"],
    )


def downgrade():
    op.drop_index("ix_listing_media_image_hash", table_name="listing_media")
    op.drop_column("listing_media", "image_hash")