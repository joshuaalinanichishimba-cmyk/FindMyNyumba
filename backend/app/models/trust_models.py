"""
app/models/trust_models.py

Trust & Safety tables for FindMyNyumba.

These plug into the SAME declarative Base and conventions as the rest of the
codebase (see admin_models.py): integer PKs, FKs to users.id / listings.id,
String status columns (portable across SQLite dev + Postgres/Supabase prod),
server_default=func.now() timestamps, extend_existing so repeated imports are
safe.

IMPORTANT — what we DO NOT re-create here:
  * audit_logs           -> already exists as admin_models.AuditLog. We reuse it
                            through app.core.audit.record_audit(). Do not add a
                            second audit table.
  * the User verification fields (verification_status, verification_doc1_url,
    verification_doc2_url, is_verified, phone_number) already exist on the User
    model. We extend that with a structured `verifications` workflow table here,
    but the boolean flags on User stay the source of truth for "is this person
    verified right now".

After adding this file, import the models in main.py BEFORE
Base.metadata.create_all (see the wiring snippet in
TRUST_SAFETY_IMPLEMENTATION.md). create_all then creates the tables on next
startup — no Alembic migration required for the dev cycle. The matching
PostgreSQL DDL (with the append-only audit trigger) lives in
app/db/trust_schema.sql for production.
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


# ── Landlord / user verification workflow ─────────────────────────────────────
# One row per verification *case*. A landlord who is rejected and re-applies
# gets a new row, so we keep the full history. The current decision is mirrored
# onto User.verification_status for fast reads everywhere else.
class Verification(Base):
    __tablename__ = "verifications"
    __table_args__ = {"extend_existing": True}

    id        = Column(Integer, primary_key=True, index=True)
    user_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Channel checks (mirrors the 6-step workflow in the brief).
    phone_verified = Column(Boolean, default=False, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    nrc_front_uploaded = Column(Boolean, default=False, nullable=False)
    nrc_back_uploaded  = Column(Boolean, default=False, nullable=False)
    selfie_uploaded    = Column(Boolean, default=False, nullable=False)
    property_docs_uploaded = Column(Boolean, default=False, nullable=False)

    # Workflow: pending | review | approved | rejected
    status            = Column(String, default="pending", nullable=False, index=True)
    rejection_reason  = Column(Text, nullable=True)

    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now())

    documents = relationship(
        "VerificationDocument",
        back_populates="verification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# Each uploaded artifact (NRC front/back, selfie, property doc) is its own row,
# pointing at a Cloudinary secure_url. We never store the raw bytes in Postgres.
class VerificationDocument(Base):
    __tablename__ = "verification_documents"
    __table_args__ = {"extend_existing": True}

    id              = Column(Integer, primary_key=True, index=True)
    verification_id = Column(Integer, ForeignKey("verifications.id"),
                             nullable=False, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"),
                             nullable=False, index=True)

    # nrc_front | nrc_back | selfie | property_doc
    doc_type    = Column(String, nullable=False, index=True)
    file_url    = Column(String, nullable=False)        # Cloudinary secure_url
    mime_type   = Column(String, nullable=True)
    # Perceptual hash of the image, used by duplicate detection to catch the
    # same NRC/selfie reused across multiple "landlord" accounts.
    phash       = Column(String, nullable=True, index=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    verification = relationship("Verification", back_populates="documents")


# ── Property verification workflow ────────────────────────────────────────────
# A listing-level review: are the photos real, does the location check out, are
# the ownership documents valid. Separate from the listing's admin
# approve/reject (which is about whether it can go live at all).
class PropertyVerification(Base):
    __tablename__ = "property_verifications"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"),
                         nullable=False, index=True)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Reviewer checklist (NULL = not yet checked).
    photos_ok    = Column(Boolean, nullable=True)
    location_ok  = Column(Boolean, nullable=True)
    documents_ok = Column(Boolean, nullable=True)

    # Workflow: pending | verified | rejected
    status            = Column(String, default="pending", nullable=False, index=True)
    rejection_reason  = Column(Text, nullable=True)

    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now())


# ── Fraud reports ─────────────────────────────────────────────────────────────
# This is the structured Trust & Safety report. The legacy `reports` table
# (models/report.py) stays for backward compatibility; new listing/landlord
# scam reports flow through here with the richer category set and the
# Submitted -> Assigned -> Investigating -> Resolved workflow from the brief.
class FraudReport(Base):
    __tablename__ = "fraud_reports"
    __table_args__ = (
        Index("ix_fraud_reports_status_created", "status", "created_at"),
        {"extend_existing": True},
    )

    id          = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=True, index=True)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # scam | fake_photos | wrong_location | fake_landlord |
    # viewing_fee_request | agent_fee_scam | other
    category    = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Workflow: submitted | assigned | investigating | resolved
    status      = Column(String, default="submitted", nullable=False, index=True)
    # When resolved: action_taken e.g. "listing removed", "landlord suspended",
    # "no action — false report".
    resolution  = Column(Text, nullable=True)

    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Captured at submission for abuse-tracing (rate limiting is the front line;
    # this is the audit trail).
    ip_address  = Column(String, nullable=True)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())


# ── Risk scores ───────────────────────────────────────────────────────────────
# One current row per user (and optionally per listing). Recomputed by
# app.core.risk_engine whenever a verification decision, report, or listing
# change happens. We store the score so the admin queue can sort by it without
# recomputing on every page load.
class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=True, index=True)

    # 0-100. Higher = safer (low risk). See risk_engine for the band mapping.
    score      = Column(Integer, nullable=False, default=50, index=True)
    band       = Column(String, nullable=False, default="medium", index=True)  # high|medium|low
    # JSON string breakdown of what drove the score, for admin transparency.
    factors    = Column(Text, nullable=True)

    computed_at = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now())


# ── Trust banners ─────────────────────────────────────────────────────────────
# Admin-editable rotating safety messages. The frontend pulls active banners
# and rotates them client-side; storing them here means copy can change without
# a redeploy.
class TrustBanner(Base):
    __tablename__ = "trust_banners"
    __table_args__ = {"extend_existing": True}

    id        = Column(Integer, primary_key=True, index=True)
    message   = Column(String, nullable=False)
    # info | warning | success — drives the dot colour on the frontend.
    level     = Column(String, nullable=False, default="info")
    icon      = Column(String, nullable=True)        # optional emoji/FA class
    # Comma-separated page keys the banner shows on, or "all".
    # e.g. "home,listings,property,dashboard_student,dashboard_landlord"
    pages     = Column(String, nullable=False, default="all")
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())
