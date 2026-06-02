"""
app/models/listing_media.py

Multi-media storage for listings (photos + videos).

A Listing can have between 1 and 20 media files. Each row here is ONE file.
The parent Listing keeps its legacy `image_url` column untouched, so older
listings and any code still reading `image_url` keep working.

Storage:
    Files live on Cloudinary. We persist BOTH the delivery URL (`media_url`,
    what the frontend renders) AND the Cloudinary `public_id` + `resource_type`,
    so deletion is reliable (no re-deriving ids from the URL).

Portability:
    media_type is a plain String (not a native DB enum) guarded by a CHECK
    constraint, so the same model runs on PostgreSQL (Supabase) and SQLite.
"""
from __future__ import annotations

import enum

from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, DateTime,
    ForeignKey, CheckConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class MediaType(str, enum.Enum):
    PHOTO = "photo"
    VIDEO = "video"


class ListingMedia(Base):
    __tablename__ = "listing_media"
    __table_args__ = (
        CheckConstraint(
            "media_type IN ('photo', 'video')",
            name="ck_listing_media_type",
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)

    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Cloudinary delivery URL — what <img>/<video> render.
    media_url = Column(String, nullable=False)

    # Cloudinary public_id (e.g. "findmynyumba/properties/ab12cd34") and the
    # resource_type used at upload ("image" | "video"). Both needed for a clean
    # destroy() on delete. NULL on rows backfilled from legacy image_url.
    public_id = Column(String, nullable=True, index=True)
    resource_type = Column(String, nullable=True)  # "image" | "video"

    # "photo" | "video" — derived server-side from real bytes, never trusted
    # from the client.
    media_type = Column(String, nullable=False, default=MediaType.PHOTO.value)

    # Best-effort metadata (from Cloudinary's upload response).
    file_name = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=True)   # bytes
    mime_type = Column(String, nullable=True)        # e.g. "image/jpeg"
    width = Column(Integer, nullable=True)           # px
    height = Column(Integer, nullable=True)          # px
    duration = Column(Float, nullable=True)          # seconds (videos only)

    # Display order within a listing (0-based; lower shown first). Not unique:
    # ordering is owned by the application layer to keep reorder simple.
    position = Column(Integer, nullable=False, default=0, index=True)

    # The cover/primary file. "Exactly one cover" is enforced in app logic, not
    # a partial unique index, to stay portable across Postgres/SQLite.
    is_cover = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    listing = relationship("Listing", back_populates="media")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ListingMedia id={self.id} listing={self.listing_id} "
            f"type={self.media_type} pos={self.position} cover={self.is_cover}>"
        )
