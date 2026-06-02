"""create listing_media and backfill from listings.image_url

Revision ID: 20260601_listing_media
Revises:
Create Date: 2026-06-01

FIRST migration in backend/alembic/versions (there was no prior chain).

IMPORTANT — this migration is primarily a BACKFILL, not a deploy dependency.
In production the `listing_media` table is created automatically by
Base.metadata.create_all() in scripts/init_and_restore.py (ListingMedia is now
registered in app/models/__init__.py). This migration:

  - creates the table only if it does not already exist (idempotent), so it is
    safe whether or not create_all already made it, and
  - backfills existing listings' image_url into listing_media rows so old
    listings appear in the new gallery.

Run it ONCE if you want existing listings backfilled:
    alembic -c alembic.ini upgrade head
Most current data is dev/test, so skipping the backfill is acceptable; the app
works either way (legacy listings fall back to image_url via cover_url).

Dialect-aware (boolean literal) and safe to re-run.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260601_listing_media"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "listing_media"):
        op.create_table(
            "listing_media",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "listing_id", sa.Integer(),
                sa.ForeignKey("listings.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column("media_url", sa.String(), nullable=False),
            sa.Column("public_id", sa.String(), nullable=True),
            sa.Column("resource_type", sa.String(), nullable=True),
            sa.Column("media_type", sa.String(), nullable=False, server_default="photo"),
            sa.Column("file_name", sa.String(), nullable=True),
            sa.Column("file_size", sa.BigInteger(), nullable=True),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("duration", sa.Float(), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.CheckConstraint("media_type IN ('photo', 'video')", name="ck_listing_media_type"),
        )
        op.create_index("ix_listing_media_public_id", "listing_media", ["public_id"])
        op.create_index("ix_listing_media_position", "listing_media", ["position"])

    # Backfill — copy each non-empty image_url into a cover photo row, but only
    # for listings that have no media yet (idempotent).
    true_lit = "1" if bind.dialect.name == "sqlite" else "TRUE"
    op.execute(
        f"""
        INSERT INTO listing_media
            (listing_id, media_url, media_type, position, is_cover)
        SELECT l.id, l.image_url, 'photo', 0, {true_lit}
        FROM listings AS l
        WHERE l.image_url IS NOT NULL
          AND l.image_url <> ''
          AND NOT EXISTS (
              SELECT 1 FROM listing_media AS m WHERE m.listing_id = l.id
          );
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "listing_media"):
        try:
            op.drop_index("ix_listing_media_position", table_name="listing_media")
            op.drop_index("ix_listing_media_public_id", table_name="listing_media")
        except Exception:
            pass
        op.drop_table("listing_media")
    # listings.image_url is intentionally left intact.
