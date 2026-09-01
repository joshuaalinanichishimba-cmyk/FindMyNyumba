"""
Site settings endpoints.

GET  /site-settings        — public. Footer and legal/policy pages read the
                             business name, support contact, SLA, etc.
PUT  /admin/site-settings  — admin only. Edit those values from the dashboard
                             without a redeploy.

Single-row model (id=1). The PUT upserts that row.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin
from app.models.site_settings import SiteSettings
from app.models.user import User

router = APIRouter()


def _dict(row: SiteSettings) -> dict:
    return {
        "legal_name":         row.legal_name,
        "trading_name":       row.trading_name,
        "pacra_number":       row.pacra_number,
        "support_email":      row.support_email,
        "support_phone":      row.support_phone,
        "website_url":        row.website_url,
        "facebook_url":       row.facebook_url,
        "instagram_url":      row.instagram_url,
        "tiktok_url":         row.tiktok_url,
        "twitter_url":        row.twitter_url,
        "whatsapp_url":       row.whatsapp_url,
        "registered_address": row.registered_address,
        "support_sla":        row.support_sla,
        "platform_name":      row.platform_name,
        "require_approval":   row.require_approval,
        "maintenance_mode":   row.maintenance_mode,
    }


def _get_or_create(db: Session) -> SiteSettings:
    row = db.query(SiteSettings).filter(SiteSettings.id == 1).first()
    if not row:
        row = SiteSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/site-settings")
def get_site_settings(db: Session = Depends(get_db)):
    """Public. Business/contact info for the footer and policy pages."""
    row = db.query(SiteSettings).filter(SiteSettings.id == 1).first()
    if not row:
        return {}
    return _dict(row)


class SiteSettingsUpdate(BaseModel):
    legal_name:         Optional[str]  = None
    trading_name:       Optional[str]  = None
    pacra_number:       Optional[str]  = None
    support_email:      Optional[str]  = None
    support_phone:      Optional[str]  = None
    website_url:        Optional[str]  = None
    facebook_url:       Optional[str]  = None
    instagram_url:      Optional[str]  = None
    tiktok_url:         Optional[str]  = None
    twitter_url:        Optional[str]  = None
    whatsapp_url:       Optional[str]  = None
    registered_address: Optional[str]  = None
    support_sla:        Optional[str]  = None
    platform_name:      Optional[str]  = None
    require_approval:   Optional[bool] = None
    maintenance_mode:   Optional[bool] = None


@router.put("/admin/site-settings")
def update_site_settings(
    payload: SiteSettingsUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin only. Update any provided business/contact/legal field."""
    row = _get_or_create(db)
    data = payload.dict(exclude_unset=True)
    for field, value in data.items():
        if hasattr(row, field):
            if isinstance(value, str):
                value = value.strip() or None
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _dict(row)
