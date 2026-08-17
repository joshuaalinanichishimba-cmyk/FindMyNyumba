"""
app/api/v1/endpoints/packages.py
FindMyNyumba SERVICE-FEE packages (Connect / Assisted Move / Escort Assist).
Public GET for the payment page; CEO/admin-only writes with price history.
NEVER touches listings.price - service fees and rent are separate systems.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require
from app.models.user import User
from app.models.service_package import ServicePackage, ServicePackagePriceHistory

router = APIRouter(tags=["Service Packages"])

PRICING_PERM = "settings.pricing"


def _pkg_dict(p):
    return {
        "id": p.id, "code": p.code, "name": p.name,
        "service_fee": float(p.service_fee) if p.service_fee is not None else None,
        "currency": p.currency, "duration_days": p.duration_days,
        "features": p.features or [], "description": p.description,
        "is_active": p.is_active, "sort_order": p.sort_order,
    }


@router.get("/packages")
def list_active_packages(db: Session = Depends(get_db)):
    pkgs = (db.query(ServicePackage)
              .filter(ServicePackage.is_active == True)  # noqa: E712
              .order_by(ServicePackage.sort_order).all())
    return [_pkg_dict(p) for p in pkgs]


@router.get("/admin/packages")
def admin_list_packages(admin: User = Depends(require(PRICING_PERM)),
                        db: Session = Depends(get_db)):
    pkgs = db.query(ServicePackage).order_by(ServicePackage.sort_order).all()
    return [_pkg_dict(p) for p in pkgs]


class PackageUpdate(BaseModel):
    name: Optional[str] = None
    service_fee: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = None
    duration_days: Optional[int] = Field(None, ge=1)
    features: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    reason: Optional[str] = None


@router.put("/admin/packages/{pkg_id}")
def admin_update_package(pkg_id: int, payload: PackageUpdate,
                         admin: User = Depends(require(PRICING_PERM)),
                         db: Session = Depends(get_db)):
    p = db.query(ServicePackage).filter(ServicePackage.id == pkg_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Package not found.")
    old_fee = float(p.service_fee) if p.service_fee is not None else None
    if payload.name is not None: p.name = payload.name.strip()
    if payload.currency is not None: p.currency = payload.currency.strip().upper()
    if payload.duration_days is not None: p.duration_days = payload.duration_days
    if payload.features is not None: p.features = [f.strip() for f in payload.features if f and f.strip()]
    if payload.description is not None: p.description = payload.description.strip()
    if payload.is_active is not None: p.is_active = payload.is_active
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
