"""
app/models/service_package.py
FindMyNyumba SERVICE fees (Connect / Assisted Move / Escort Assist).
These are the fees a student pays FindMyNyumba for verified-access services.
They are COMPLETELY SEPARATE from accommodation rental price (listings.price):
nothing here ever reads or writes a listing price, and vice versa.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime, ForeignKey, JSON
from app.core.database import Base


class ServicePackage(Base):
    __tablename__ = "service_packages"

    id            = Column(Integer, primary_key=True, index=True)
    code          = Column(String, unique=True, nullable=False, index=True)  # student_connect / assisted_move / escort_assist
    name          = Column(String, nullable=False)
    service_fee   = Column(Numeric, nullable=False)          # the FindMyNyumba fee (NOT rent)
    currency      = Column(String, default="ZMW", nullable=False)
    duration_days = Column(Integer, default=30, nullable=False)
    features      = Column(JSON, nullable=True)              # list of feature strings
    description   = Column(Text, nullable=True)
    is_active     = Column(Boolean, default=True, nullable=False)
    sort_order    = Column(Integer, default=0, nullable=False)
    audience      = Column(String, default="student", index=True)   # student | landlord
    grant_type    = Column(String, default="student_access")        # student_access | listing_boost
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ServicePackagePriceHistory(Base):
    __tablename__ = "service_package_price_history"

    id          = Column(Integer, primary_key=True, index=True)
    package_id  = Column(Integer, ForeignKey("service_packages.id"), nullable=False, index=True)
    package_code= Column(String, nullable=False)
    old_fee     = Column(Numeric, nullable=True)
    new_fee     = Column(Numeric, nullable=False)
    currency    = Column(String, default="ZMW", nullable=False)
    changed_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_by_name = Column(String, nullable=True)
    reason      = Column(Text, nullable=True)
    changed_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
