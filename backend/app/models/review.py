"""
app/models/review.py

A rating + written comment a student leaves on a listing.

WHAT CHANGED vs the old version
-------------------------------
- Foreign key was `property_id -> properties.id` (a dead/legacy table). It now
  correctly points at `listing_id -> listings.id`, matching where listings
  actually live.
- Added a `status` column ('pending' | 'approved' | 'rejected') so reviews are
  moderated by an admin before they show publicly. New reviews start 'pending'.
- This model was never registered in main.py, so the table was never created
  and every submitted review was silently discarded. It is now registered.

extend_existing=True matches the rest of your models and is harmless if the
table is created fresh.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"),    nullable=False, index=True)
    user_name   = Column(String)                       # snapshot of author name at submit time
    rating      = Column(Integer, nullable=False)      # 1..5 (validated in the endpoint)
    comment     = Column(Text)
    status      = Column(String, nullable=False, default="pending", index=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    reply_text  = Column(Text, nullable=True)        # host's public reply to this review
    reply_at    = Column(DateTime(timezone=True), nullable=True)
    rating_accuracy      = Column(Integer, nullable=True)  # was it as described?
    rating_landlord      = Column(Integer, nullable=True)  # communication / helpfulness
    rating_value         = Column(Integer, nullable=True)  # worth the price
