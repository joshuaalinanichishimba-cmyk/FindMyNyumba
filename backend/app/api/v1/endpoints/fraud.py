"""
app/api/v1/endpoints/fraud.py

The REPORT system — the button on every listing.

Routes (mounted under /api/v1):
    POST /fraud/reports            submit a report (auth required, rate limited)
    GET  /fraud/reports/mine       reports the current user has filed

Categories: scam | fake_photos | wrong_location | fake_landlord |
            viewing_fee_request | agent_fee_scam | other
Workflow:   submitted -> assigned -> investigating -> resolved
            (the assigned/investigating/resolved transitions are admin-only and
             live in admin_trust.py)

WHY a fresh table instead of the legacy /reports: the brief's category set and
the assignment workflow are richer than the old `reports` table, and keeping
Trust & Safety reports separate makes the admin queue and SLA reporting clean.
The old endpoint keeps working for anything still pointing at it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.audit import record_audit
from app.core.database import get_db
from app.core.notify import push_notification  # best-effort admin broadcast
from app.core.rate_limiter import limiter, REPORT_LIMIT
from app.models.listing import Listing
from app.models.user import User
from app.models.trust_models import FraudReport
from app.schemas.trust import FraudReportCreate, FraudReportOut

router = APIRouter(prefix="/fraud", tags=["Fraud Reports"])


@router.post("/reports", response_model=FraudReportOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(REPORT_LIMIT)   # 10/hour per IP — anti abuse-report-bombing
def submit_report(
    body: FraudReportCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # If a listing is named, resolve its owner so the report attaches to the
    # person, not just the post (the post can be deleted; the account persists).
    reported_user_id = body.reported_user_id
    if body.listing_id and not reported_user_id:
        listing = db.query(Listing).filter(Listing.id == body.listing_id).first()
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found.")
        reported_user_id = listing.owner_id

    # Stop trivially self-serving / nonsense reports against yourself.
    if reported_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot report yourself.")

    ip = request.client.host if request.client else None
    report = FraudReport(
        reporter_id=current_user.id,
        listing_id=body.listing_id,
        reported_user_id=reported_user_id,
        category=body.category,
        description=body.description,
        status="submitted",
        ip_address=ip,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    record_audit(db, request, actor=current_user, action="fraud_report.submitted",
                 entity_type="fraud_report", entity_id=report.id,
                 meta={"category": body.category, "listing_id": body.listing_id})

    # Best-effort admin ping; never break the request if notify is unavailable.
    try:
        push_notification(
            db,
            user_id=None,           # None = admin broadcast
            ntype="report",
            title="New fraud report",
            body=f"{body.category} report filed (#{report.id}).",
        )
    except Exception:
        pass

    return report


@router.get("/reports/mine", response_model=list[FraudReportOut])
def my_reports(current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return (
        db.query(FraudReport)
        .filter(FraudReport.reporter_id == current_user.id)
        .order_by(FraudReport.created_at.desc())
        .all()
    )
