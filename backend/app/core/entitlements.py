"""
app/core/entitlements.py
SINGLE SOURCE OF TRUTH for "does this user have paid access right now".

Replaces three divergent copies that each hardcoded a 30 day window:
  - messages.py    _has_paid_access          (defined twice, identical)
  - listings.py    _student_has_paid_access

That hardcoding was a real defect: assisted_move and escort_assist are 60 day
packages, so those students silently lost messaging and landlord contact
access on day 31 of access they had paid for.

Access is now driven by service_subscriptions.expires_at, which the backend
calculates from the purchased package's duration_days at settlement time.

Never trust the client for any of this. Every value here is server derived.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger("fmn.entitlements")

# Fallback window for payments made before service_subscriptions existed.
# Keeps already paying students working after deploy. Safe to remove once all
# legacy 30 day transactions have aged out.
LEGACY_FALLBACK_DAYS = 30


def _now():
    return datetime.now(timezone.utc)


def get_active_subscription(db: Session, user_id):
    """Returns the live subscription with the furthest expiry, or None."""
    if not user_id:
        return None
    try:
        from app.models.service_subscription import ServiceSubscription
    except Exception:
        return None

    return (db.query(ServiceSubscription)
              .filter(ServiceSubscription.user_id == user_id,
                      ServiceSubscription.status == "active",
                      ServiceSubscription.expires_at > _now())
              .order_by(ServiceSubscription.expires_at.desc())
              .first())


def _legacy_has_paid_access(db: Session, user_id) -> bool:
    """Pre subscription behaviour: any successful fee in the last 30 days."""
    from app.models.admin_models import Transaction
    cutoff = _now() - timedelta(days=LEGACY_FALLBACK_DAYS)
    return db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.type == "verification_fee",
        Transaction.status == "success",
        Transaction.created_at >= cutoff,
    ).first() is not None


def has_active_access(db: Session, user_id) -> bool:
    """
    True if the user currently holds paid FindMyNyumba service access.
    Checks real subscriptions first, then falls back to the legacy rule so
    students who paid before this system existed are not cut off.
    """
    if not user_id:
        return False
    if get_active_subscription(db, user_id) is not None:
        return True
    return _legacy_has_paid_access(db, user_id)


def access_summary(db: Session, user_id) -> dict:
    """Safe to return to the owning user. Contains no internal fields."""
    sub = get_active_subscription(db, user_id)
    if sub:
        remaining = (sub.expires_at - _now()).days
        return {
            "has_access": True,
            "package": sub.package_code,
            "package_name": sub.package_name,
            "expires_at": sub.expires_at.isoformat(),
            "days_remaining": max(0, remaining),
            "source": "subscription",
        }
    if has_active_access(db, user_id):
        return {"has_access": True, "source": "legacy"}
    return {"has_access": False}


def grant_access(db: Session, user_id, package, transaction=None):
    """
    Creates the access window after a VERIFIED successful payment.

    Call this ONLY from the payment settlement path, never from a request
    handler acting on client input. Idempotent per transaction: the unique
    constraint on transaction_id means a replayed webhook cannot double grant.
    """
    from app.models.service_subscription import ServiceSubscription

    txn_id = getattr(transaction, "id", None)
    if txn_id:
        existing = (db.query(ServiceSubscription)
                      .filter(ServiceSubscription.transaction_id == txn_id)
                      .first())
        if existing:
            return existing

    duration = int(getattr(package, "duration_days", 0) or 0)
    if duration <= 0:
        logger.error("grant_access: package %s has no duration; defaulting to %s days",
                     getattr(package, "code", "?"), LEGACY_FALLBACK_DAYS)
        duration = LEGACY_FALLBACK_DAYS

    starts = _now()
    sub = ServiceSubscription(
        user_id=user_id,
        package_id=getattr(package, "id", None),
        transaction_id=txn_id,
        package_code=getattr(package, "code", "unknown"),
        package_name=getattr(package, "name", None),
        amount_paid=getattr(transaction, "amount", None),
        currency=getattr(transaction, "currency", None) or getattr(package, "currency", "ZMW"),
        duration_days=duration,
        starts_at=starts,
        expires_at=starts + timedelta(days=duration),
        status="active",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    logger.info("access.granted user=%s package=%s days=%s expires=%s txn=%s",
                user_id, sub.package_code, duration, sub.expires_at, txn_id)
    return sub
