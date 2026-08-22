"""
app/models/price_review.py
Accommodation PRICE REVIEW (Stage 2).

A price review is a STUDENT data point about a listing's rent: "this looks too
high", "I actually paid K1,800", "this is accurate". Reviews are admin
moderated: they land `pending` and only move a listing's confidence once a
staff member accepts them.

SEPARATION RULE (must always hold):
  listings.price is the LANDLORD's number and is NEVER written here.
  Accepted reviews only populate the listing's ANNOTATION fields
  (market_low, market_high, price_confidence, price_review_status,
  price_last_reviewed_at). We surround the landlord's price with confidence;
  we never overwrite it.

This is the accommodation-rent side. It has no relationship to FindMyNyumba
service fees (service_packages), which are a separate system.

Money is stored as Float to match listings.price (Float).
"""
from sqlalchemy import (Column, Integer, String, Text, Float,
                        DateTime, ForeignKey, Index)
from sqlalchemy.sql import func

from app.core.database import Base


REVIEW_TYPES = ("too_high", "too_low", "confirmed_accurate", "paid_different")
REVIEW_STATUSES = ("pending", "accepted", "dismissed")


class PriceReview(Base):
    __tablename__ = "price_reviews"

    id = Column(Integer, primary_key=True, index=True)

    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # too_high | too_low | confirmed_accurate | paid_different
    review_type = Column(String, nullable=False, index=True)

    # The rent the student cites. Null is valid for confirmed_accurate.
    reported_price = Column(Float, nullable=True)
    currency = Column(String, nullable=True, default="ZMW")
    note = Column(Text, nullable=True)

    # Snapshot of listings.price at submission, so later landlord edits do not
    # rewrite what the student was reacting to.
    listed_price_at_review = Column(Float, nullable=True)

    # pending | accepted | dismissed
    status = Column(String, nullable=False, default="pending", index=True)

    moderated_by = Column(Integer, nullable=True)
    moderated_by_name = Column(String, nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    moderation_note = Column(Text, nullable=True)

    # Landlord right of reply. Column built now; UI deferred to a later stage.
    landlord_response = Column(Text, nullable=True)
    landlord_responded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_price_reviews_listing_status", "listing_id", "status"),
    )

    def __repr__(self):
        return (f"<PriceReview listing={self.listing_id} "
                f"type={self.review_type} status={self.status}>")
