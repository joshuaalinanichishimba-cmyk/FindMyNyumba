"""
app/api/v1/endpoints/admin_router.py

FULL IMPLEMENTATION.

Endpoints the admin.html frontend calls:
  GET  /admin/stats
  GET  /admin/users
  POST /admin/users/{id}/suspend
  GET  /admin/all-listings
  PATCH /admin/listings/{id}/approve
  PATCH /admin/listings/{id}/reject
  DELETE /admin/listings/{id}
  GET  /admin/verifications
  POST /admin/verifications/{id}/approve
  POST /admin/verifications/{id}/reject
  GET  /admin/reports
  PATCH /admin/reports/{id}/dismiss
  GET  /admin/analytics/growth
  POST /admin/announcements
  POST /admin/settings/update
  POST /admin/change-password

FIX vs previous version:
  - GET /admin/verifications previously returned placeholder document URLs
    ({user_id}_doc1_placeholder). Landlords.py saves files as
    "{user_id}_doc1_{rand}_{original_name}" and "{user_id}_doc2_{rand}_{original_name}".
    The endpoint now scans the verification upload directory to find the actual
    filenames for each user and returns absolute URLs the admin can open directly.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.sessions import revoke_all_for_user
from app.core.security import get_password_hash, verify_password
from app.models.listing import Listing
from app.models.message import Message
from app.models.report import Report
from app.models.review import Review
from app.models.student_review import StudentReview
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["Admin"])

VERIFY_DIR = Path("static/uploads/verification")


# â”€â”€ Role guard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _get_verification_docs(user, request: Request = None) -> list:
    """
    Return the user's verification documents from the Cloudinary URLs stored
    on their account. (Previously scanned local disk, which Render wipes on
    every deploy.) `request` is kept for signature compatibility but unused.
    """
    return [
        {"label": "ID Document",        "url": getattr(user, "verification_doc1_url", None)},
        {"label": "Ownership Document", "url": getattr(user, "verification_doc2_url", None)},
    ]

    prefix = f"{user_id}_"
    base_url = str(request.base_url).rstrip("/")

    doc1_files = sorted(VERIFY_DIR.glob(f"{user_id}_doc1_*"))
    doc2_files = sorted(VERIFY_DIR.glob(f"{user_id}_doc2_*"))

    if doc1_files:
        docs.append({
            "label": "ID Document",
            "url":   f"{base_url}/static/uploads/verification/{doc1_files[-1].name}",
        })
    else:
        docs.append({"label": "ID Document", "url": None})

    if doc2_files:
        docs.append({
            "label": "Ownership Document",
            "url":   f"{base_url}/static/uploads/verification/{doc2_files[-1].name}",
        })
    else:
        docs.append({"label": "Ownership Document", "url": None})

    return docs


# â”€â”€ GET /admin/stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/stats")
def get_stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    total_users      = db.query(User).count()
    total_listings   = db.query(Listing).count()
    total_messages   = db.query(Message).count()
    pending_listings = db.query(Listing).filter(Listing.status == "pending").count()
    pending_verifs   = db.query(User).filter(
        User.verification_status == "pending",
        User.role.in_(["landlord", "student_host", "student"]),
    ).count()
    pending_reports  = db.query(Report).filter(Report.status == "pending").count()

    return {
        "total_users":      total_users,
        "total_listings":   total_listings,
        "total_messages":   total_messages,
        "pending_listings": pending_listings,
        "pending_verifs":   pending_verifs,
        "pending_reports":  pending_reports,
    }


# â”€â”€ GET /admin/users â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/users")
def get_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id":                  u.id,
            "full_name":           u.full_name,
            "email":               u.email,
            "role":                u.role,
            "is_active":           u.is_active,
            "is_verified":         u.is_verified,
            "verification_status": u.verification_status or "unverified",
            "created_at":          u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


# â”€â”€ POST /admin/users/{id}/suspend â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.post("/users/{user_id}/suspend")
def toggle_suspend(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot suspend your own account.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = not user.is_active
    db.commit()
    if not user.is_active:
        revoke_all_for_user(db, user.id)
    action = "suspended" if not user.is_active else "reinstated"
    return {"status": "success", "message": f"User {action}.", "is_active": user.is_active}


# â”€â”€ GET /admin/all-listings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/all-listings")
def get_all_listings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    listings = db.query(Listing).order_by(Listing.created_at.desc()).all()
    return [
        {
            "id":         l.id,
            "title":      l.title,
            "location":   l.location,
            "price":      l.price,
            "status":     l.status,
            "is_boosted": l.is_boosted,
            "owner_id":   l.owner_id,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in listings
    ]


# â”€â”€ PATCH /admin/listings/{id}/approve â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.patch("/listings/{listing_id}/approve")
def approve_listing(listing_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status = "active"
    db.commit()
    return {"status": "success", "message": "Listing approved and now live."}


# â”€â”€ PATCH /admin/listings/{id}/reject â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.patch("/listings/{listing_id}/reject")
def reject_listing(listing_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status = "rejected"
    db.commit()
    return {"status": "success", "message": "Listing rejected."}


# â”€â”€ DELETE /admin/listings/{id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.delete("/listings/{listing_id}")
def delete_listing(listing_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    db.delete(listing)
    db.commit()
    return {"status": "success", "message": "Listing deleted."}


# â”€â”€ GET /admin/verifications â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/verifications")
def get_verifications(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Return landlords, student_hosts, and students with pending verification.
    Document URLs are resolved by scanning the verification upload directory
    for files matching the user's ID pattern, so admins can actually open them.
    """
    users = db.query(User).filter(
        User.verification_status == "pending",
        User.role.in_(["landlord", "student_host", "student"]),
    ).order_by(User.created_at.asc()).all()

    return [
        {
            "id":                  u.id,
            "full_name":           u.full_name,
            "email":               u.email,
            "role":                u.role,
            "verification_status": u.verification_status,
            "documents":           _get_verification_docs(u, request),
        }
        for u in users
    ]


# â”€â”€ POST /admin/verifications/{id}/approve â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.post("/verifications/{user_id}/approve")
def approve_verification(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.verification_status = "verified"
    user.is_verified          = True
    db.commit()
    return {"status": "success", "message": f"{user.full_name} has been verified."}


# â”€â”€ POST /admin/verifications/{id}/reject â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ResolveBody(BaseModel):
    resolution: str


class RejectPayload(BaseModel):
    reason: Optional[str] = None

@router.post("/verifications/{user_id}/reject")
def reject_verification(
    user_id: int,
    payload: RejectPayload,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.verification_status           = "rejected"
    user.verification_rejection_reason = payload.reason or "Documents were not accepted."
    db.commit()
    return {"status": "success", "message": "Verification rejected."}


# â”€â”€ GET /admin/reports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# â”€â”€ GET /admin/reports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/reports")
def get_reports(
    status_filter: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Report).order_by(Report.created_at.desc())
    if status_filter:
        q = q.filter(Report.status == status_filter)
    reports = q.all()

    # Batch-fetch names to avoid N+1
    reporter_ids = {r.reporter_id for r in reports}
    handler_ids  = {r.handled_by for r in reports if r.handled_by}
    listing_ids  = {r.listing_id for r in reports if r.listing_id}
    user_ids     = reporter_ids | handler_ids
    users        = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    listings     = {l.id: l for l in db.query(Listing).filter(Listing.id.in_(listing_ids)).all()} if listing_ids else {}

    return [
        {
            "id":             r.id,
            "listing_id":     r.listing_id,
            "listing_title":  listings[r.listing_id].title if r.listing_id and r.listing_id in listings else None,
            "reporter_id":    r.reporter_id,
            "reporter_name":  users[r.reporter_id].full_name if r.reporter_id in users else "Unknown",
            "reporter_email": users[r.reporter_id].email     if r.reporter_id in users else "",
            "reason":         r.reason,
            "description":    r.description,
            "status":         r.status,
            "resolution":     r.resolution,
            "handled_by":     r.handled_by,
            "handled_by_name": users[r.handled_by].full_name if r.handled_by and r.handled_by in users else None,
            "handled_at":     r.handled_at.isoformat() if r.handled_at else None,
            "created_at":     r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


# â”€â”€ PATCH /admin/reports/{id}/investigate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.patch("/reports/{report_id}/investigate")
def investigate_report(report_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    report.status = "investigating"
    report.handled_by = admin.id
    report.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Report marked as investigating."}


# â”€â”€ PATCH /admin/reports/{id}/resolve â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.patch("/reports/{report_id}/resolve")
def resolve_report(report_id: int, body: ResolveBody, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    report.status = "resolved"
    report.resolution = body.resolution
    report.handled_by = admin.id
    report.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Report resolved."}


# â”€â”€ PATCH /admin/reports/{id}/dismiss â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.patch("/reports/{report_id}/dismiss")
def dismiss_report(report_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    report.status = "dismissed"
    report.handled_by = admin.id
    report.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Report dismissed."}


# â”€â”€ GET /admin/analytics/growth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/analytics/growth")
def get_growth(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Returns monthly user and listing registration counts for the last 6 months.
    Uses Python-side grouping for cross-DB compatibility.
    """
    from collections import defaultdict
    from datetime import date

    today = date.today()
    months = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12; y -= 1
        months.append((y, m))

    def label(y, m):
        return datetime(y, m, 1).strftime("%b %Y")

    cutoff = datetime(months[0][0], months[0][1], 1, tzinfo=timezone.utc)

    all_users    = db.query(User.created_at).filter(User.created_at    >= cutoff).all()
    all_listings = db.query(Listing.created_at).filter(Listing.created_at >= cutoff).all()

    user_counts    = defaultdict(int)
    listing_counts = defaultdict(int)

    for (dt,) in all_users:
        if dt:
            key = (dt.year, dt.month)
            user_counts[key] += 1

    for (dt,) in all_listings:
        if dt:
            key = (dt.year, dt.month)
            listing_counts[key] += 1

    return {
        "months":   [label(y, m) for y, m in months],
        "users":    [user_counts.get((y, m), 0)    for y, m in months],
        "listings": [listing_counts.get((y, m), 0) for y, m in months],
    }


# â”€â”€ POST /admin/announcements â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class AnnouncementPayload(BaseModel):
    title:  str
    body:   str
    target: str = "all"   # all | student | landlord | student_host

@router.post("/announcements")
def send_announcement(
    payload: AnnouncementPayload,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not payload.title.strip() or not payload.body.strip():
        raise HTTPException(status_code=400, detail="Title and message body are required.")

    target_roles = (
        ["student", "landlord", "student_host"]
        if payload.target == "all"
        else [payload.target]
    )
    users = db.query(User).filter(User.role.in_(target_roles), User.is_active == True).all()

    for user in users:
        msg = Message(
            sender_id   = admin.id,
            receiver_id = user.id,
            content     = f"[ANNOUNCEMENT] {payload.title}\n\n{payload.body}",
            is_read     = False,
        )
        db.add(msg)
    db.commit()

    return {"status": "success", "message": f"Announcement sent to {len(users)} users."}


# â”€â”€ POST /admin/settings/update â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class SettingsPayload(BaseModel):
    platform_name:    Optional[str]  = None
    support_email:    Optional[str]  = None
    require_approval: Optional[bool] = None
    maintenance_mode: Optional[bool] = None

@router.post("/settings/update")
def update_settings(
    payload: SettingsPayload,
    admin: User = Depends(require_admin),
):
    # TODO: persist to a settings table or env override in production.
    return {"status": "success", "message": "Settings saved."}


# â”€â”€ POST /admin/change-password â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class AdminChangePasswordPayload(BaseModel):
    old_password:     str
    new_password:     str
    confirm_password: str

@router.post("/change-password")
def change_password(
    payload: AdminChangePasswordPayload,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    if not verify_password(payload.old_password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
    if not PWD_RE.match(payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ characters with uppercase, lowercase, number, and special character.",
        )

    admin.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "success", "message": "Password changed successfully."}
@router.post("/migrate-images")
async def migrate_broken_images(db: Session = Depends(get_db)):
    """ONE-TIME migration: nulls out local image URLs that will never load on Render."""
    from app.models.listing import Listing
    listings = db.query(Listing).all()
    fixed = []
    for l in listings:
        if l.image_url and not l.image_url.startswith("https://"):
            fixed.append({"id": l.id, "title": l.title, "old_url": l.image_url})
            l.image_url = None
    db.commit()
    return {"fixed": len(fixed), "listings": fixed}
# ==================================================
# REVIEWS MODERATION
# ==================================================
@router.get("/reviews")
def admin_list_reviews(status: str = "pending", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(Review)
    if status:
        q = q.filter(Review.status == status)
    rows = q.order_by(Review.created_at.desc()).all()
    out = []
    for r in rows:
        listing = db.query(Listing).filter(Listing.id == r.listing_id).first()
        out.append({
            "id": r.id,
            "listing_id": r.listing_id,
            "listing_title": listing.title if listing else None,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "rating": r.rating,
            "comment": r.comment,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


@router.patch("/reviews/{review_id}/approve")
def admin_approve_review(review_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    r.status = "approved"
    db.commit()
    return {"id": r.id, "status": r.status}


@router.patch("/reviews/{review_id}/reject")
def admin_reject_review(review_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    r.status = "rejected"
    db.commit()
    return {"id": r.id, "status": r.status}


# ==================================================
# SUPPORT / CONVERSATIONS
# ==================================================
@router.get("/conversations")
def admin_list_conversations(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    msgs = db.query(Message).order_by(Message.created_at.desc()).all()
    threads = {}
    name_cache = {}

    def name_of(uid):
        if uid not in name_cache:
            u = db.query(User).filter(User.id == uid).first()
            name_cache[uid] = u.full_name if u else f"User {uid}"
        return name_cache[uid]

    for m in msgs:
        pair = tuple(sorted([m.sender_id, m.receiver_id]))
        key = (pair, m.property_id)
        if key not in threads:
            threads[key] = {
                "participants": [
                    {"id": pair[0], "name": name_of(pair[0])},
                    {"id": pair[1], "name": name_of(pair[1])},
                ],
                "property_id": m.property_id,
                "last_message": m.content,
                "last_at": m.created_at.isoformat() if m.created_at else None,
                "unread": 0,
                "count": 0,
            }
        threads[key]["count"] += 1
        if not m.is_read:
            threads[key]["unread"] += 1

    return list(threads.values())


# ==================================================
# STUDENT REVIEWS MODERATION (host -> student, two-way reputation)
# Mirrors the property-review moderation so approved student reviews surface.
# ==================================================
@router.get("/student-reviews")
def admin_list_student_reviews(status: str = "pending", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(StudentReview)
    if status:
        q = q.filter(StudentReview.status == status)
    rows = q.order_by(StudentReview.created_at.desc()).all()
    out = []
    for r in rows:
        student = db.query(User).filter(User.id == r.student_id).first()
        out.append({
            "id": r.id,
            "student_id": r.student_id,
            "student_name": student.full_name if student else None,
            "landlord_id": r.landlord_id,
            "landlord_name": r.landlord_name,
            "viewing_id": r.viewing_id,
            "rating": r.rating,
            "comment": r.comment,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


@router.patch("/student-reviews/{review_id}/approve")
def admin_approve_student_review(review_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(StudentReview).filter(StudentReview.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Student review not found")
    r.status = "approved"
    db.commit()
    return {"id": r.id, "status": r.status}


@router.patch("/student-reviews/{review_id}/reject")
def admin_reject_student_review(review_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(StudentReview).filter(StudentReview.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Student review not found")
    r.status = "rejected"
    db.commit()
    return {"id": r.id, "status": r.status}
