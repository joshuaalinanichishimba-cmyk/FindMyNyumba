"""
app/models/listing_event.py

Lightweight engagement events for listings (views, contacts, saves).
One row per event; admin analytics aggregate these. actor_id is nullable
because public browsing is often anonymous.

Register in main.py before create_all so the table is created.
"""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class ListingEvent(Base):
    __tablename__ = "listing_events"
    __table_args__ = {"extend_existing": True}

    id         = Column(BigInteger, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    kind       = Column(String, nullable=False, index=True)   # 'view' | 'contact' | 'save'
    actor_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
