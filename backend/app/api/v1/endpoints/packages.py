"""
app/api/v1/endpoints/packages.py
FindMyNyumba SERVICE FEE packages.
Public GET for the payment pages; CEO/admin only writes with price history.
NEVER touches listings.price - service fees and rent are separate systems.

AUDIENCE
Packages are scoped to who buys them:
  student  -> shown on pay-verified-access.html (Connect / Assist tiers)
  landlord -> future landlord facing purchases (e.g. Fast Tenant boost)
The public endpoint defaults to `student`, so adding a landlord package can
never make it appear on the student payment page by accident.

GRANT TYPE
Records what a successful purchase unlocks:
  student_access -> messaging + landlord contact for duration_days
  listing_boost  -> time boxed featured placement on the buyer's listings
Only student_access is wired to activation today (see core/entitlements.py).
listing_boost packages can be created and priced but purchase activation is
not yet implemented; keep them inactive until it is.
"""
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require
from app.models.user import User
from app.models.service_package import ServicePackage, ServicePackagePriceHistory

router = APIRouter(tags=["Service Packages"])

PRICING_PERM = "settings.pricing"

VALID_AUDIENCES = ("student", "landlord")
VALID_GRANT_TYPES = ("student_access", "listing_boost")

# Codes become part of the payment reference (FMN-STUDENT-CONNECT-...), so keep
# them to a safe charset.
CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


def _pkg_dict(p):
    return {
        "id": p.id, "code": p.code, "name": p.name,
        "service_fee": float(p.service_fee) if p.service_fee is not None else None,
        "currency": p.currency, "duration_days": p.duration_days,
        "features": p.features or [], "description": p.description,
        "is_active": p.is_active, "sort_order": p.sort_order,
        "audience": getattr(p, "audience", None) or "student",
        "grant_type": getattr(p, "grant_type", None) or "student_access",
    }


@router.get("/packages")
def list_active_packages(audience: str = Query("student"),
                         db: Session = Depends(get_db)):
    """Public. Defaults to student facing packages only."""
    aud = (audience or "student").strip().lower()
    if aud not in VALID_AUDIENCES:
        raise HTTPException(status_code=400, detail="Unknown audience.")

    q = db.query(ServicePackage).filter(ServicePackage.is_active == True)  # noqa: E712
    if hasattr(ServicePackage, "audience"):
        q = q.filter(ServicePackage.audience == aud)
    pkgs = q.order_by(ServicePackage.sort_order).all()
    return [_pkg_dict(p) for p in pkgs]


@router.get("/admin/packages")
def admin_list_packages(admin: User = Depends(require(PRICING_PERM)),
                        db: Session = Depends(get_db)):
    """Admin sees every package across all audiences, active or not."""
    pkgs = db.query(ServicePackage).order_by(ServicePackage.sort_order).all()
    return [_pkg_dict(p) for p in pkgs]


class PackageCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=48)
    name: str = Field(..., min_length=2, max_length=120)
    service_fee: float = Field(..., ge=0)
    currency: str = "ZMW"
    duration_days: int = Field(..., ge=1)
    features: Optional[List[str]] = None
    description: Optional[str] = None
    audience: str = "student"
    grant_type: str = "student_access"
    is_active: bool = False          # created inactive on purpose
    sort_order: Optional[int] = None


@router.post("/admin/packages", status_code=201)
def admin_create_package(payload: PackageCreate,
                         admin: User = Depends(require(PRICING_PERM)),
                         db: Session = Depends(get_db)):
    """
    Create a new service package.

    Defaults to INACTIVE so a half configured package can never be sold by
    accident. The admin flips it active once the details are right.
    """
    code = payload.code.strip().lower()
    if not CODE_RE.match(code):
        raise HTTPException(
            status_code=400,
            detail="Code must be lowercase letters, numbers and underscores, starting with a letter.")

    aud = payload.audience.strip().lower()
    if aud not in VALID_AUDIENCES:
        raise HTTPException(status_code=400, detail="Unknown audience.")

    grant = payload.grant_type.strip().lower()
    if grant not in VALID_GRANT_TYPES:
        raise HTTPException(status_code=400, detail="Unknown grant type.")

    # Boost purchase activation is implemented; boost packages may be active.

    if db.query(ServicePackage).filter(ServicePackage.code == code).first():
        raise HTTPException(status_code=409, detail="A package with that code already exists.")

    if payload.sort_order is not None:
        sort_order = payload.sort_order
    else:
        highest = db.query(ServicePackage).order_by(ServicePackage.sort_order.desc()).first()
        sort_order = ((highest.sort_order or 0) + 1) if highest else 1

    pkg = ServicePackage(
        code=code,
        name=payload.name.strip(),
        service_fee=payload.service_fee,
        currency=(payload.currency or "ZMW").strip().upper(),
        duration_days=payload.duration_days,
        features=[f.strip() for f in (payload.features or []) if f and f.strip()],
        description=(payload.description or "").strip() or None,
        is_active=payload.is_active,
        sort_order=sort_order,
    )
    if hasattr(pkg, "audience"):
        pkg.audience = aud
    if hasattr(pkg, "grant_type"):
        pkg.grant_type = grant

    db.add(pkg)
    try:
        db.commit()
        db.refresh(pkg)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A package with that code already exists.")

    # Opening price is recorded so history is complete from day one.
    db.add(ServicePackagePriceHistory(
        package_id=pkg.id, package_code=pkg.code,
        old_fee=None, new_fee=payload.service_fee, currency=pkg.currency,
        changed_by=admin.id, changed_by_name=getattr(admin, "full_name", None),
        reason="Package created",
    ))
    db.commit()

    return _pkg_dict(pkg)


class PackageUpdate(BaseModel):
    name: Optional[str] = None
    service_fee: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = None
    duration_days: Optional[int] = Field(None, ge=1)
    features: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    audience: Optional[str] = None
    grant_type: Optional[str] = None
    sort_order: Optional[int] = None
    reason: Optional[str] = None


@router.put("/admin/packages/{pkg_id}")
def admin_update_package(pkg_id: int, payload: PackageUpdate,
                         admin: User = Depends(require(PRICING_PERM)),
                         db: Session = Depends(get_db)):
    p = db.query(ServicePackage).filter(ServicePackage.id == pkg_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Package not found.")

    old_fee = float(p.service_fee) if p.service_fee is not None else None

    if payload.audience is not None:
        aud = payload.audience.strip().lower()
        if aud not in VALID_AUDIENCES:
            raise HTTPException(status_code=400, detail="Unknown audience.")
        if hasattr(p, "audience"):
            p.audience = aud

    if payload.grant_type is not None:
        grant = payload.grant_type.strip().lower()
        if grant not in VALID_GRANT_TYPES:
            raise HTTPException(status_code=400, detail="Unknown grant type.")
        if hasattr(p, "grant_type"):
            p.grant_type = grant

    # Boost purchase activation is implemented; boost packages may be active.

    if payload.name is not None:
        p.name = payload.name.strip()
    if payload.currency is not None:
        p.currency = payload.currency.strip().upper()
    if payload.duration_days is not None:
        p.duration_days = payload.duration_days
    if payload.features is not None:
        p.features = [f.strip() for f in payload.features if f and f.strip()]
    if payload.description is not None:
        p.description = payload.description.strip()
    if payload.is_active is not None:
        p.is_active = payload.is_active
    if payload.sort_order is not None:
        p.sort_order = payload.sort_order

    fee_changed = payload.service_fee is not None and float(payload.service_fee) != (old_fee or 0)
    if payload.service_fee is not None:
        p.service_fee = payload.service_fee

    if fee_changed:
        db.add(ServicePackagePriceHistory(
            package_id=p.id, package_code=p.code,
            old_fee=old_fee, new_fee=payload.service_fee, currency=p.currency,
            changed_by=admin.id, changed_by_name=getattr(admin, "full_name", None),
            reason=(payload.reason or None),
        ))

    db.commit()
    db.refresh(p)
    return _pkg_dict(p)


@router.get("/admin/packages/{pkg_id}/history")
def admin_package_history(pkg_id: int,
                          admin: User = Depends(require(PRICING_PERM)),
                          db: Session = Depends(get_db)):
    rows = (db.query(ServicePackagePriceHistory)
              .filter(ServicePackagePriceHistory.package_id == pkg_id)
              .order_by(ServicePackagePriceHistory.changed_at.desc()).all())
    return [{
        "old_fee": float(r.old_fee) if r.old_fee is not None else None,
        "new_fee": float(r.new_fee) if r.new_fee is not None else None,
        "currency": r.currency, "changed_by_name": r.changed_by_name,
        "reason": r.reason,
        "changed_at": r.changed_at.isoformat() if r.changed_at else None,
    } for r in rows]
