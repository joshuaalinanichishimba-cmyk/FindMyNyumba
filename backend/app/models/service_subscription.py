"""
app/models/service_subscription.py
Time bound access granted by a verified successful payment.

The expiry is calculated by the BACKEND from the purchased package's
duration_days at the moment of settlement, and is then frozen. Changing a
package's price or duration later never alters access already sold.

This is the FindMyNyumba SERVICE side only. It has no relationship to
accommodation rent (listings.price), which is a separate system.
"""
from sqlalchemy import (Column, Integer, String, DateTime, Numeric,
                        ForeignKey, Index)
from sqlalchemy.sql import func

from app.core.database import Base


class ServiceSubscription(Base):
    __tablename__ = "service_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    package_id = Column(Integer, nullable=True)
    transaction_id = Column(Integer, nullable=True, unique=True, index=True)

    # Terms as purchased. Snapshotted so later admin edits cannot rewrite history.
    package_code = Column(String, nullable=False, index=True)
    package_name = Column(String, nullable=True)
    amount_paid = Column(Numeric(12, 2), nullable=True)
    currency = Column(String, nullable=True, default="ZMW")
    duration_days = Column(Integer, nullable=False)

    starts_at = Column(DateTime(timezone=True), nullable=False,
                       server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # active | expired | cancelled
    status = Column(String, nullable=False, default="active", index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_service_subs_user_expiry", "user_id", "expires_at"),
    )

    def __repr__(self):
        return (f"<ServiceSubscription user={self.user_id} "
                f"pkg={self.package_code} expires={self.expires_at}>")
