"""
app/schemas/trust.py

Pydantic v2 schemas for the Trust & Safety API. These are the validation
boundary: every value that reaches an endpoint body is constrained here
(enums via Literal, length caps, trimming), which is the first line of defence
against injection and junk data. SQLAlchemy parameter binding handles the
SQL-injection layer; these schemas handle "is this even a sensible value".
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Allowed enums kept here so the API and DB never drift.
ReportCategory = Literal[
    "scam", "fake_photos", "wrong_location", "fake_landlord",
    "viewing_fee_request", "agent_fee_scam", "other",
]
ReportStatus = Literal["submitted", "assigned", "investigating", "resolved"]
VerificationStatus = Literal["pending", "review", "approved", "rejected"]
PropertyVerificationStatus = Literal["pending", "verified", "rejected"]
BannerLevel = Literal["info", "warning", "success"]
DocType = Literal["nrc_front", "nrc_back", "selfie", "property_doc"]


# ── Trust banners ─────────────────────────────────────────────────────────────
class TrustBannerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    message: str
    level: BannerLevel
    icon: Optional[str] = None
    pages: str
    sort_order: int


class TrustBannerCreate(BaseModel):
    message: str = Field(min_length=4, max_length=240)
    level: BannerLevel = "info"
    icon: Optional[str] = Field(default=None, max_length=40)
    pages: str = Field(default="all", max_length=200)
    sort_order: int = 0
    is_active: bool = True

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class TrustBannerUpdate(BaseModel):
    message: Optional[str] = Field(default=None, min_length=4, max_length=240)
    level: Optional[BannerLevel] = None
    icon: Optional[str] = Field(default=None, max_length=40)
    pages: Optional[str] = Field(default=None, max_length=200)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# ── Verification badges (public read model) ───────────────────────────────────
class BadgeOut(BaseModel):
    """Resolved badge state for a user or listing — what the frontend renders."""
    # verified_landlord | verified_property | phone_verified |
    # identity_submitted | unverified
    key: str
    label: str
    level: Literal["green", "yellow", "red"]


# ── Landlord verification workflow ────────────────────────────────────────────
class VerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    phone_verified: bool
    email_verified: bool
    nrc_front_uploaded: bool
    nrc_back_uploaded: bool
    selfie_uploaded: bool
    property_docs_uploaded: bool
    status: VerificationStatus
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class VerificationDecision(BaseModel):
    """Admin approve/reject payload."""
    approve: bool
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def _require_reason_on_reject(cls, v, info):
        # If rejecting, a reason is mandatory (enforced again in the endpoint
        # for a clean 400 message).
        return v.strip() if isinstance(v, str) else v


# ── Property verification ─────────────────────────────────────────────────────
class PropertyVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    listing_id: int
    photos_ok: Optional[bool] = None
    location_ok: Optional[bool] = None
    documents_ok: Optional[bool] = None
    status: PropertyVerificationStatus
    rejection_reason: Optional[str] = None
    created_at: datetime


class PropertyVerificationDecision(BaseModel):
    photos_ok: bool
    location_ok: bool
    documents_ok: bool
    approve: bool
    reason: Optional[str] = Field(default=None, max_length=500)


# ── Fraud reports ─────────────────────────────────────────────────────────────
class FraudReportCreate(BaseModel):
    category: ReportCategory
    listing_id: Optional[int] = None
    reported_user_id: Optional[int] = None
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class FraudReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: ReportCategory
    status: ReportStatus
    listing_id: Optional[int] = None
    reported_user_id: Optional[int] = None
    description: Optional[str] = None
    resolution: Optional[str] = None
    created_at: datetime


class FraudReportAssign(BaseModel):
    assignee_id: Optional[int] = None   # default: the acting admin


class FraudReportResolve(BaseModel):
    resolution: str = Field(min_length=3, max_length=1000)


class StatusUpdate(BaseModel):
    status: ReportStatus


# ── Risk score (read model) ───────────────────────────────────────────────────
class RiskScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: Optional[int] = None
    listing_id: Optional[int] = None
    score: int
    band: Literal["high", "medium", "low"]
    factors: Optional[str] = None
    computed_at: Optional[datetime] = None


# ── Admin trust dashboard summary ─────────────────────────────────────────────
class TrustDashboardOut(BaseModel):
    total_verified_landlords: int
    pending_verifications: int
    scam_reports: int
    open_reports: int
    high_risk_accounts: int
    suspended_accounts: int
