"""
SiteSettings — a single-row table holding business / legal / contact info that
appears on the public site (footer, policy pages) and is editable from the admin
dashboard without a redeploy.

Kept as one row (id=1). The GET endpoint is public (footer + policy pages read
it); the PUT endpoint is admin-guarded. Compliance-facing fields (legal name,
support contact, SLA, registered address) are here so they can be corrected to
the real PACRA-registered details from the admin UI once known.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class SiteSettings(Base):
    __tablename__ = "site_settings"

    id = Column(Integer, primary_key=True, index=True)

    # Business / legal identity
    legal_name         = Column(String, nullable=True)   # PACRA-registered name
    trading_name       = Column(String, nullable=True)   # brand: FindMyNyumba
    pacra_number       = Column(String, nullable=True)   # registration number, if any

    # Contact
    support_email      = Column(String, nullable=True)
    support_phone      = Column(String, nullable=True)
    website_url        = Column(String, nullable=True)
    registered_address = Column(Text,   nullable=True)

    # Service commitments
    support_sla        = Column(String, nullable=True)   # e.g. "within 1 business day"

    # Operational toggles (carried over from the old settings stub)
    platform_name      = Column(String,  nullable=True)
    require_approval    = Column(Boolean, nullable=True)  # listings need admin approval
    maintenance_mode    = Column(Boolean, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
