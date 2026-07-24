"""add student-facing property attributes to listings

Revision ID: 20260724_listing_attrs
Revises: 20260629_txn_momo
Create Date: 2026-07-24

All columns are nullable so existing rows and code paths are unaffected.
property type reuses the existing listing_type column.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260724_listing_attrs"
down_revision = "20260629_txn_momo"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("listings", sa.Column("bedrooms", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("bathrooms", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("furnished", sa.String(), nullable=True))
    op.add_column("listings", sa.Column("water_supply", sa.String(), nullable=True))
    op.add_column("listings", sa.Column("electricity", sa.String(), nullable=True))
    op.add_column("listings", sa.Column("parking", sa.String(), nullable=True))
    op.add_column("listings", sa.Column("curfew", sa.String(), nullable=True))
    op.add_column("listings", sa.Column("gender_preference", sa.String(), nullable=True))
    op.add_column("listings", sa.Column("distance_to_campus", sa.String(), nullable=True))
    op.add_column("listings", sa.Column("amenities", sa.Text(), nullable=True))


def downgrade():
    for col in ("amenities", "distance_to_campus", "gender_preference", "curfew",
                "parking", "electricity", "water_supply", "furnished",
                "bathrooms", "bedrooms"):
        op.drop_column("listings", col)
