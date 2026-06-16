"""
app/api/v1/endpoints/admin_trust.py

ADMIN / Trust & Safety team console. Every route requires staff (admin or
moderator) and writes an append-only audit row on each decision.

Sections:
  Dashboard      GET  /admin/trust/dashboard
  Verifications  GET  /admin/trust/verifications
                 GET  /admin/trust/verifications/{id}
                 POST /admin/trust/verifications/{id}/decision
  Property       GET  /admin/trust/property-verifications
                 POST /admin/trust/property-verifications/{id}/decision
  Reports        GET  /admin/trust/reports
                 POST /admin/trust/reports/{id}/assign
                 POST /admin/trust/reports/{id}/status
                 POST /admin/trust/reports/{id}/resolve
  Risk           GET  /admin/trust/risk/high
                 POST /admin/trust/risk/recompute/{user_id}
  Banners        GET/POST/PATCH/DELETE /admin/trust/banners
  Duplicates     GET  /admin/trust/duplicates

Audit logs themselves are read through the existing admin audit endpoints; this
module only WRITES to them (via record_audit), never deletes — the brief's
"nothing should be deletable" rule is enforced at the DB layer in
trust_schema.sql (trigger blocks UPDATE/DELETE on audit_logs).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.notify import push_notification
from app.core.permissions import require_staff, require_admin
from app.core.risk_engine import persist_user_risk
from app.models.listing import Listing
from app.models.user import User
from app.models.trust_models import (
    Verification, VerificationDocument, PropertyVerification,
    FraudReport, RiskScore, TrustBanner,
)
from app.schemas.trust import (
    TrustDashboardOut, VerificationOut, VerificationDecision,
    PropertyVerificationOut, PropertyVerificationDecision,
    FraudReportOut, FraudReportAssign, FraudReportResolve, StatusUpdate,
    RiskScoreOut, TrustBannerOut, TrustBannerCreate, TrustBannerUpdate,
)

router = APIRouter(prefix="/admin/trust", tags=["Admin: Trust & Safety"])


def _now():
    return datetime.now(timezone.utc)


# ── Dashboard ─────────────────────────────────────────────────────────────────
@router.get("/dashboard", response_model=TrustDashboardOut)
def dashboard(staff: User = Depends(require_staff), db: Session = Depends(get_db)):
    total_verified_landlords = (
        db.query(func.count(User.id))
        .filter(User.role.in_(["landlord", "student_host"]),
                User.verification_status == "approved")
        .scalar()
    ) or 0
    pending_verifications = (
        db.query(func.count(Verification.id))
        .filter(Verification.status.in_(["pending", "review"]))
        .scalar()
    ) or 0
    scam_reports = (
        db.query(func.count(FraudReport.id))
        .filter(FraudReport.category.in_(
            ["scam", "fake_landlord", "viewing_fee_request", "agent_fee_scam"]))
        .scalar()
    ) or 0
    open_reports = (
        db.query(func.count(FraudReport.id))
        .filter(FraudReport.status != "resolved")
        .scalar()
    ) or 0
    high_risk_accounts = (
        db.query(func.count(RiskScore.id))
        .filter(RiskScore.band == "high", RiskScore.user_id.isnot(None))
        .scalar()
    ) or 0
    suspended_accounts = (
        db.query(func.count(User.id)).filter(User.is_active.is_(False)).scalar()
    ) or 0

    return TrustDashboardOut(
        total_verified_landlords=total_verified_landlords,
        pending_verifications=pending_verifications,
        scam_reports=scam_reports,
        open_reports=open_reports,
        high_risk_accounts=high_risk_accounts,
        suspended_accounts=suspended_accounts,
    )


# ── Verification queue ────────────────────────────────────────────────────────
@router.get("/verifications", response_model=list[VerificationOut])
def list_verifications(status_filter: str = "review",
                       staff: User = Depends(require_staff),
                       db: Session = Depends(get_db)):
    q = db.query(Verification)
    if status_filter and status_filter != "all":
        q = q.filter(Verification.status == status_filter)
    return q.order_by(Verification.created_at.asc()).all()


@router.get("/verifications/{vid}")
def verification_detail(vid: int, staff: User = Depends(require_staff),
                        db: Session = Depends(get_db)):
    v = db.query(Verification).filter(Verification.id == vid).first()
    if v is None:
        raise HTTPException(status_code=404, detail="Verification not found.")
    docs = db.query(VerificationDocument).filter(
        VerificationDocument.verification_id == vid).all()
    user = db.query(User).filter(User.id == v.user_id).first()
    return {
        "verification": VerificationOut.model_validate(v),
        "user": {"id": user.id, "full_name": user.full_name,
                 "email": user.email, "phone_number": user.phone_number,
                 "role": user.role} if user else None,
        "documents": [
            {"doc_type": d.doc_type, "file_url": d.file_url,
             "mime_type": d.mime_type, "phash": d.phash} for d in docs
        ],
    }


@router.post("/verifications/{vid}/decision", response_model=VerificationOut)
def decide_verification(vid: int, body: VerificationDecision, request: Request,
                        staff: User = Depends(require_staff),
                        db: Session = Depends(get_db)):
    v = db.query(Verification).filter(Verification.id == vid).first()
    if v is None:
        raise HTTPException(status_code=404, detail="Verification not found.")
    if not body.approve and not (body.reason and body.reason.strip()):
        raise HTTPException(status_code=400, detail="A reason is required to reject.")

    user = db.query(User).filter(User.id == v.user_id).first()
    if body.approve:
        v.status = "approved"
        v.rejection_reason = None
        if user:
            user.verification_status = "approved"
            user.is_verified = True
    else:
        v.status = "rejected"
        v.rejection_reason = body.reason.strip()
        if user:
            user.verification_status = "rejected"
            user.verification_rejection_reason = body.reason.strip()

    v.reviewed_by = staff.id
    v.reviewed_at = _now()
    db.commit()
    db.refresh(v)

    record_audit(db, request, actor=staff,
                 action="verification.approved" if body.approve else "verification.rejected",
                 entity_type="verification", entity_id=v.id,
                 meta={"reason": body.reason} if not body.approve else None)

    if user:
        persist_user_risk(db, user)
        push_notification(
            db, user_id=user.id, ntype="verification",
            title="Verification " + ("approved" if body.approve else "rejected"),
            body=(None if body.approve else f"Reason: {body.reason}"),
        )
    return v


# ── Property verification queue ───────────────────────────────────────────────
@router.get("/property-verifications", response_model=list[PropertyVerificationOut])
def list_property_verifications(status_filter: str = "pending",
                                staff: User = Depends(require_staff),
                                db: Session = Depends(get_db)):
    q = db.query(PropertyVerification)
    if status_filter and status_filter != "all":
        q = q.filter(PropertyVerification.status == status_filter)
    return q.order_by(PropertyVerification.created_at.asc()).all()


@router.post("/property-verifications/{pid}/decision",
             response_model=PropertyVerificationOut)
def decide_property(pid: int, body: PropertyVerificationDecision, request: Request,
                    staff: User = Depends(require_staff),
                    db: Session = Depends(get_db)):
    pv = db.query(PropertyVerification).filter(PropertyVerification.id == pid).first()
    if pv is None:
        raise HTTPException(status_code=404, detail="Property verification not found.")
    if not body.approve and not (body.reason and body.reason.strip()):
        raise HTTPException(status_code=400, detail="A reason is required to reject.")

    pv.photos_ok = body.photos_ok
    pv.location_ok = body.location_ok
    pv.documents_ok = body.documents_ok
    pv.status = "verified" if body.approve else "rejected"
    pv.rejection_reason = None if body.approve else body.reason.strip()
    pv.reviewed_by = staff.id
    pv.reviewed_at = _now()
    db.commit()
    db.refresh(pv)

    record_audit(db, request, actor=staff,
                 action="property_verification.verified" if body.approve
                 else "property_verification.rejected",
                 entity_type="listing", entity_id=pv.listing_id,
                 meta={"reason": body.reason} if not body.approve else None)

    # Bump the owner's risk score (a verified property is a positive signal).
    listing = db.query(Listing).filter(Listing.id == pv.listing_id).first()
    if listing:
        owner = db.query(User).filter(User.id == listing.owner_id).first()
        if owner:
            persist_user_risk(db, owner)
    return pv


# ── Fraud report workflow ─────────────────────────────────────────────────────
@router.get("/reports", response_model=list[FraudReportOut])
def list_reports(status_filter: str = "submitted",
                 staff: User = Depends(require_staff),
                 db: Session = Depends(get_db)):
    q = db.query(FraudReport)
    if status_filter and status_filter != "all":
        q = q.filter(FraudReport.status == status_filter)
    return q.order_by(FraudReport.created_at.asc()).all()


@router.post("/reports/{rid}/assign", response_model=FraudReportOut)
def assign_report(rid: int, body: FraudReportAssign, request: Request,
                  staff: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    r = db.query(FraudReport).filter(FraudReport.id == rid).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    r.assigned_to = body.assignee_id or staff.id
    r.assigned_at = _now()
    if r.status == "submitted":
        r.status = "assigned"
    db.commit()
    db.refresh(r)
    record_audit(db, request, actor=staff, action="fraud_report.assigned",
                 entity_type="fraud_report", entity_id=r.id,
                 meta={"assignee_id": r.assigned_to})
    return r


@router.post("/reports/{rid}/status", response_model=FraudReportOut)
def update_report_status(rid: int, body: StatusUpdate, request: Request,
                         staff: User = Depends(require_staff),
                         db: Session = Depends(get_db)):
    r = db.query(FraudReport).filter(FraudReport.id == rid).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    r.status = body.status
    db.commit()
    db.refresh(r)
    record_audit(db, request, actor=staff, action="fraud_report.status_changed",
                 entity_type="fraud_report", entity_id=r.id,
                 meta={"status": body.status})
    return r


@router.post("/reports/{rid}/resolve", response_model=FraudReportOut)
def resolve_report(rid: int, body: FraudReportResolve, request: Request,
                   staff: User = Depends(require_staff),
                   db: Session = Depends(get_db)):
    r = db.query(FraudReport).filter(FraudReport.id == rid).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    r.status = "resolved"
    r.resolution = body.resolution.strip()
    r.resolved_by = staff.id
    r.resolved_at = _now()
    db.commit()
    db.refresh(r)
    record_audit(db, request, actor=staff, action="fraud_report.resolved",
                 entity_type="fraud_report", entity_id=r.id,
                 meta={"resolution": body.resolution})
    # Recompute risk for the reported party (a resolved report changes weight).
    if r.reported_user_id:
        u = db.query(User).filter(User.id == r.reported_user_id).first()
        if u:
            persist_user_risk(db, u)
    return r


# ── Risk scores ───────────────────────────────────────────────────────────────
@router.get("/risk/high", response_model=list[RiskScoreOut])
def high_risk_accounts(staff: User = Depends(require_staff),
                       db: Session = Depends(get_db)):
    return (
        db.query(RiskScore)
        .filter(RiskScore.band == "high", RiskScore.user_id.isnot(None))
        .order_by(RiskScore.score.asc())
        .limit(200)
        .all()
    )


@router.post("/risk/recompute/{user_id}", response_model=RiskScoreOut)
def recompute_risk(user_id: int, request: Request,
                   staff: User = Depends(require_staff),
                   db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    row = persist_user_risk(db, user)
    record_audit(db, request, actor=staff, action="risk.recomputed",
                 entity_type="user", entity_id=user_id,
                 meta={"score": row.score, "band": row.band})
    return row


# ── Trust banner management ───────────────────────────────────────────────────
@router.get("/banners", response_model=list[TrustBannerOut])
def admin_list_banners(staff: User = Depends(require_staff),
                       db: Session = Depends(get_db)):
    return db.query(TrustBanner).order_by(
        TrustBanner.sort_order.asc(), TrustBanner.id.asc()).all()


@router.post("/banners", response_model=TrustBannerOut, status_code=201)
def create_banner(body: TrustBannerCreate, request: Request,
                  staff: User = Depends(require_admin),  # banners = admin only
                  db: Session = Depends(get_db)):
    b = TrustBanner(**body.model_dump(), created_by=staff.id)
    db.add(b)
    db.commit()
    db.refresh(b)
    record_audit(db, request, actor=staff, action="trust_banner.created",
                 entity_type="trust_banner", entity_id=b.id)
    return b


@router.patch("/banners/{bid}", response_model=TrustBannerOut)
def update_banner(bid: int, body: TrustBannerUpdate, request: Request,
                  staff: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    b = db.query(TrustBanner).filter(TrustBanner.id == bid).first()
    if b is None:
        raise HTTPException(status_code=404, detail="Banner not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(b, field, value)
    db.commit()
    db.refresh(b)
    record_audit(db, request, actor=staff, action="trust_banner.updated",
                 entity_type="trust_banner", entity_id=b.id)
    return b


@router.delete("/banners/{bid}", status_code=204)
def delete_banner(bid: int, request: Request,
                  staff: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    b = db.query(TrustBanner).filter(TrustBanner.id == bid).first()
    if b is None:
        raise HTTPException(status_code=404, detail="Banner not found.")
    # Soft-disable rather than hard delete keeps history clean and reversible.
    b.is_active = False
    db.commit()
    record_audit(db, request, actor=staff, action="trust_banner.disabled",
                 entity_type="trust_banner", entity_id=b.id)
    return None


# ── Duplicate image report ────────────────────────────────────────────────────
@router.get("/duplicates")
def duplicate_groups(staff: User = Depends(require_staff),
                     db: Session = Depends(get_db)):
    """
    Group verification documents by identical perceptual hash and return any
    hash shared across MORE THAN ONE user — the reused-NRC/selfie signal.
    (Near-duplicate matching is done per-upload in verification.py; this view
    surfaces exact-hash collisions for a fast triage list.)
    """
    rows = (
        db.query(VerificationDocument.phash,
                 func.count(func.distinct(VerificationDocument.user_id)).label("users"))
        .filter(VerificationDocument.phash.isnot(None))
        .group_by(VerificationDocument.phash)
        .having(func.count(func.distinct(VerificationDocument.user_id)) > 1)
        .all()
    )
    out = []
    for phash, _ in rows:
        docs = (
            db.query(VerificationDocument)
            .filter(VerificationDocument.phash == phash)
            .all()
        )
        out.append({
            "phash": phash,
            "documents": [
                {"user_id": d.user_id, "doc_type": d.doc_type, "file_url": d.file_url}
                for d in docs
            ],
        })
    return {"groups": out, "count": len(out)}
