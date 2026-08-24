"""
app/api/v1/endpoints/payments.py
Verified Access payments via LENCO (mobile money: Airtel, MTN, Zamtel).

PRICING RULE
service_packages is the SINGLE SOURCE OF TRUTH for fee, currency and name. The
client never sends an amount and no client supplied amount is ever trusted.
Accommodation rent (listings.price) is a separate system and is never read or
written here.

STATE MACHINE
pending -> success | failed. success and failed are TERMINAL. A settled
transaction can never be reopened, downgraded or re-settled, by any code path
including webhooks and polling.

TRUST MODEL
Only Lenco may move a transaction out of pending: either a signature verified
webhook, or a server side status query. The browser can never assert success.

IDEMPOTENCY
Enforced by the unique constraint on transactions.idempotency_key, not by a
read-then-write check, so concurrent duplicate submits cannot both succeed.
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.admin_models import Transaction
from app.models.service_package import ServicePackage
from app.services import lenco_service
from app.services.lenco_service import LencoError, LencoConfigError, mask_phone

logger = logging.getLogger("fmn.payments")

router = APIRouter(prefix="/payments", tags=["payments"])

TERMINAL_STATES = ("success", "failed")

# Window in which a repeat initiate is treated as the same intent rather than a
# new charge. Protects against double taps, retries and impatient refreshes.
IDEMPOTENCY_WINDOW_SECONDS = 180

_METHOD_BY_OPERATOR = {
    "airtel": "airtel_money",
    "mtn": "mtn_money",
    "zamtel": "zamtel_money",
}

_PROVIDER_SUCCESS = ("successful", "success", "completed")
_PROVIDER_FAILED = ("failed", "cancelled", "expired", "declined", "reversed")


def _now():
    return datetime.now(timezone.utc)


def _set_provider_ref(txn: Transaction, value):
    """
    Writes provider_ref ONLY. The legacy momo_ref_id column is MTN specific and
    carries a unique constraint; putting Lenco references there would be both
    semantically wrong and a collision risk.
    """
    if value and hasattr(txn, "provider_ref"):
        txn.provider_ref = value


def _idempotency_key(user_id: int, pkg_code: str) -> str:
    """
    Deterministic per user, per package, per time bucket. The unique index on
    transactions.idempotency_key is the actual lock.
    """
    bucket = int(_now().timestamp()) // IDEMPOTENCY_WINDOW_SECONDS
    return f"va:{user_id}:{pkg_code}:{bucket}"


def _settle(db: Session, txn: Transaction, new_state: str, provider_ref=None, reason=None) -> str:
    """
    The ONLY place a transaction changes state. Enforces the state machine:
    a transaction already in a terminal state is never modified again.
    """
    current = (txn.status or "").lower()
    if current in TERMINAL_STATES:
        if current != new_state:
            logger.warning("state.blocked ref=%s attempted=%s current=%s",
                           txn.ref, new_state, current)
        return current

    if new_state not in TERMINAL_STATES:
        return current

    txn.status = new_state
    _set_provider_ref(txn, provider_ref)
    if reason and hasattr(txn, "failure_reason"):
        txn.failure_reason = reason
    db.commit()

    if new_state == "success":
        try:
            from app.core.entitlements import grant_access
            from app.models.service_package import ServicePackage
            code = (txn.ref or "").replace("FMN-", "", 1).rsplit("-", 1)[0].lower().replace("-", "_")
            pkg = db.query(ServicePackage).filter(ServicePackage.code == code).first()
            if pkg:
                if getattr(pkg, "grant_type", "student_access") == "listing_boost":
                    _activate_listing_boost(db, txn, pkg)
                else:
                    grant_access(db, txn.user_id, pkg, txn)
                _payment_success_side_effects(db, txn, pkg)
            else:
                logger.error("grant.no_package ref=%s derived_code=%s", txn.ref, code)
        except Exception:
            logger.exception("grant.failed ref=%s user=%s MANUAL GRANT REQUIRED", txn.ref, txn.user_id)

    logger.info("state.settled ref=%s state=%s amount=%s %s user=%s providerRef=%s reason=%s",
                txn.ref, new_state, txn.amount, txn.currency, txn.user_id,
                provider_ref, reason)
    return new_state


def _load_package(db: Session, code: str) -> ServicePackage:
    """
    Server authoritative price source. Refuses to proceed if the package is
    missing, inactive or unpriced. No silent fallback to a default tier:
    deactivating a package makes it unpurchasable.
    """
    if not code or not isinstance(code, str):
        raise HTTPException(status_code=400, detail="No package selected.")

    pkg = db.query(ServicePackage).filter(ServicePackage.code == code.strip()).first()
    if not pkg:
        raise HTTPException(status_code=400, detail="That package is not available.")
    if pkg.is_active is False:
        raise HTTPException(status_code=400, detail="That package is no longer available.")
    if pkg.service_fee is None or float(pkg.service_fee) <= 0:
        raise HTTPException(status_code=409, detail="That package is not priced yet.")
    return pkg


class InitiateBody(BaseModel):
    msisdn: str = Field(..., min_length=9, max_length=16)
    tier: str = Field(..., min_length=2, max_length=64)
    listing_id: int | None = None  # required only for listing_boost purchases


@router.post("/verified-access/initiate")
def initiate(body: InitiateBody,
             current_user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    pkg = _load_package(db, body.tier)
    _boost_listing_id = None
    if getattr(pkg, "grant_type", "student_access") == "listing_boost":
        if not body.listing_id:
            raise HTTPException(status_code=400, detail="A listing must be selected to boost.")
        from app.models.listing import Listing
        _lst = db.query(Listing).filter(Listing.id == body.listing_id).first()
        if not _lst:
            raise HTTPException(status_code=404, detail="Listing not found.")
        if _lst.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only boost your own listing.")
        _boost_listing_id = body.listing_id
    price = float(pkg.service_fee)          # from service_packages, never the client
    currency = (pkg.currency or "ZMW").upper()

    try:
        phone = lenco_service.normalize_phone(body.msisdn)
        operator = lenco_service.detect_operator(phone)
    except LencoError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ref = "FMN-" + pkg.code.upper().replace("_", "-") + "-" + uuid.uuid4().hex[:10].upper()
    idem = _idempotency_key(current_user.id, pkg.code)

    txn = Transaction(
        ref=ref,
        user_id=current_user.id,
        type=("boost" if _boost_listing_id else "verification_fee"),
        listing_id=_boost_listing_id,
        amount=price,
        currency=currency,
        method=_METHOD_BY_OPERATOR.get(operator, "mobile_money"),
        status="pending",
        idempotency_key=idem,
    )
    db.add(txn)
    try:
        db.commit()
        db.refresh(txn)
    except IntegrityError:
        db.rollback()
        prior = db.query(Transaction).filter(Transaction.idempotency_key == idem).first()
        if prior:
            logger.info("initiate.deduped ref=%s user=%s", prior.ref, current_user.id)
            return {
                "transaction_id": prior.id,
                "ref": prior.ref,
                "status": prior.status if prior.status in TERMINAL_STATES else "pending",
                "tier": pkg.code,
                "tier_name": pkg.name,
                "amount_display": f"{currency} {price:,.2f}",
                "deduplicated": True,
                "instruction": "Approve the payment on your phone.",
            }
        logger.warning("initiate.integrity_error ref=%s", ref)
        raise HTTPException(status_code=409, detail="Please try again.")

    # Pending row is committed BEFORE the provider call, so a crash mid flight
    # still leaves a reconcilable record rather than a silent charge.
    try:
        data = lenco_service.collect_mobile_money(
            amount=price, msisdn=phone, reference=ref, operator=operator,
        )
    except LencoConfigError:
        _settle(db, txn, "failed", reason="gateway_not_configured")
        raise HTTPException(status_code=503, detail="Payments are temporarily unavailable.")
    except LencoError as e:
        _settle(db, txn, "failed", reason="gateway_rejected")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        # Outcome genuinely unknown. Leave PENDING so reconciliation can settle
        # it. Marking failed here risks denying a student who actually paid.
        logger.exception("initiate.unknown_outcome ref=%s phone=%s", ref, mask_phone(phone))
        raise HTTPException(status_code=502,
                            detail="We could not confirm that payment. Check your phone before retrying.")

    provider_status = (data.get("status") or "pending").lower()
    _set_provider_ref(txn, data.get("lencoReference") or data.get("id"))
    db.commit()

    if provider_status in _PROVIDER_FAILED:
        _settle(db, txn, "failed", reason=data.get("reasonForFailure") or "declined")
        raise HTTPException(status_code=402, detail="That payment was declined. Please try again.")

    return {
        "transaction_id": txn.id,
        "ref": ref,
        "status": "pending",
        "provider_status": provider_status,
        "operator": operator,
        "tier": pkg.code,
        "tier_name": pkg.name,
        "amount_display": f"{currency} {price:,.2f}",
        "instruction": ("Approve the payment on your phone."
                        if provider_status == "pay-offline"
                        else "Your payment is being processed."),
    }


def _sync_from_provider(db: Session, txn: Transaction) -> dict:
    """Shared reconciliation used by both status routes."""
    if (txn.status or "").lower() in TERMINAL_STATES:
        return {"status": txn.status, "ref": txn.ref}

    try:
        data = lenco_service.get_collection_status(txn.ref)
    except LencoError:
        return {"status": "pending", "ref": txn.ref}
    except Exception:
        logger.exception("status.unexpected ref=%s", txn.ref)
        return {"status": "pending", "ref": txn.ref}

    provider_status = (data.get("status") or "").lower()
    provider_ref = data.get("lencoReference") or data.get("id")

    if provider_status in _PROVIDER_SUCCESS:
        _settle(db, txn, "success", provider_ref=provider_ref)
        return {"status": "success", "ref": txn.ref}

    if provider_status in _PROVIDER_FAILED:
        _settle(db, txn, "failed", provider_ref=provider_ref,
                reason=data.get("reasonForFailure"))
        return {"status": "failed", "ref": txn.ref}

    return {"status": "pending", "ref": txn.ref, "provider_status": provider_status}


@router.get("/{payment_id}/status")
def status_by_id(payment_id: int,
                 current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == payment_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if txn.user_id != current_user.id and getattr(current_user, "role", "") not in ("admin", "ceo"):
        raise HTTPException(status_code=403, detail="Not your transaction.")
    return _sync_from_provider(db, txn)


@router.get("/status/{reference}")
def status_by_reference(reference: str,
                        current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.ref == reference).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if txn.user_id != current_user.id and getattr(current_user, "role", "") not in ("admin", "ceo"):
        raise HTTPException(status_code=403, detail="Not your transaction.")
    return _sync_from_provider(db, txn)


@router.post("/webhook")
async def lenco_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Asynchronous settlement from Lenco.

    Unauthenticated by design: trust comes from the X-Lenco-Signature HMAC over
    the raw body, not from a session. Always returns 200 once the signature is
    valid, because Lenco retries hourly for 24 hours on any non 2xx response.
    """
    raw = await request.body()
    signature = request.headers.get("x-lenco-signature")

    if not lenco_service.verify_webhook_signature(raw, signature):
        logger.warning("webhook.rejected invalid_signature bytes=%s", len(raw))
        raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        event = await request.json()
    except Exception:
        logger.error("webhook.bad_json")
        return Response(status_code=200)

    data = event.get("data") or {}
    reference = data.get("reference")
    provider_status = (data.get("status") or "").lower()
    provider_ref = data.get("lencoReference") or data.get("id")

    if not reference:
        logger.warning("webhook.no_reference event=%s", event.get("event"))
        return Response(status_code=200)

    txn = db.query(Transaction).filter(Transaction.ref == reference).first()
    if not txn:
        logger.warning("webhook.unknown_reference ref=%s", reference)
        return Response(status_code=200)

    # Defence in depth: a webhook must never change what is owed. If the amount
    # Lenco reports does not match our record, settle nothing and alert.
    try:
        if data.get("amount") is not None and abs(float(data["amount"]) - float(txn.amount)) > 0.01:
            logger.critical("webhook.amount_mismatch ref=%s ours=%s theirs=%s",
                            reference, txn.amount, data.get("amount"))
            return Response(status_code=200)
    except (TypeError, ValueError):
        pass

    if provider_status in _PROVIDER_SUCCESS:
        _settle(db, txn, "success", provider_ref=provider_ref)
    elif provider_status in _PROVIDER_FAILED:
        _settle(db, txn, "failed", provider_ref=provider_ref,
                reason=data.get("reasonForFailure"))
    else:
        logger.info("webhook.ignored ref=%s status=%s", reference, provider_status)

    return Response(status_code=200)


def _payment_success_side_effects(db, txn, package=None):
    """
    Called once, immediately after a transaction settles to success.
    Creates an in-app Notification (type='payment') and sends a receipt email.
    Both are best-effort and independently guarded.
    """
    from app.models.user import User

    user = db.query(User).filter(User.id == txn.user_id).first()
    if not user:
        return

    pkg_name = getattr(package, "name", None) or "Verified Access"
    amount = txn.amount
    currency = txn.currency or "ZMW"
    amount_disp = (f"K{int(amount):,}" if currency == "ZMW"
                   else f"{currency} {int(amount):,}")

    # work out expiry from any subscription just granted
    expires_on = None
    try:
        from app.core.entitlements import get_active_subscription
        sub = get_active_subscription(db, txn.user_id)
        if sub and sub.expires_at:
            expires_on = sub.expires_at.strftime("%d %b %Y")
    except Exception:
        pass

    # 1) in-app notification (type 'payment' is already a valid Notification type)
    try:
        from app.models.admin_models import Notification
        body = f"Your {amount_disp} {pkg_name} payment was received."
        if expires_on:
            body += f" Access is active until {expires_on}."
        db.add(Notification(
            user_id=txn.user_id,
            type="payment",
            title="Payment received",
            body=body,
            channel="in_app",
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("notify.failed ref=%s user=%s", txn.ref, txn.user_id)

    # 2) receipt email (respects the user's email_alerts preference)
    try:
        if getattr(user, "email_alerts", True) and getattr(user, "email", None):
            from app.utils.email import send_payment_receipt_email
            send_payment_receipt_email(
                to_email=user.email,
                full_name=getattr(user, "full_name", None),
                package_name=pkg_name,
                amount=amount,
                currency=currency,
                method=txn.method,
                reference=txn.ref,
                expires_on=expires_on,
            )
    except Exception:
        logger.exception("receipt.failed ref=%s user=%s", txn.ref, txn.user_id)


def _activate_listing_boost(db, txn, package):
    """
    Turn on a time-boxed boost for the listing a boost purchase targets.

    The listing is taken from txn.listing_id (a boost purchase must record which
    listing it is for). Sets is_boosted + boost_expires_at = now + duration.
    Never touches the listing's price or content.

    Idempotent-ish: re-running extends from the later of (now, current expiry),
    so a webhook replay does not shorten an active boost.
    """
    from datetime import datetime, timedelta, timezone
    from app.models.listing import Listing

    listing_id = getattr(txn, "listing_id", None)
    if not listing_id:
        logger.error("boost.no_listing ref=%s user=%s - boost purchase had no listing_id",
                     txn.ref, txn.user_id)
        return None

    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        logger.error("boost.listing_missing ref=%s listing=%s", txn.ref, listing_id)
        return None

    duration = int(getattr(package, "duration_days", 0) or 0)
    if duration <= 0:
        duration = 30  # safe default

    now = datetime.now(timezone.utc)
    # extend rather than overwrite, so a replay/renew never shortens an active boost
    base = now
    current = getattr(listing, "boost_expires_at", None)
    if current and current > now:
        base = current

    listing.is_boosted = True
    listing.boost_expires_at = base + timedelta(days=duration)
    if hasattr(listing, "boost_tier"):
        listing.boost_tier = getattr(package, "code", None)
    if hasattr(listing, "boosted_at"):
        listing.boosted_at = now

    db.commit()
    logger.info("boost.activated ref=%s listing=%s tier=%s expires=%s",
                txn.ref, listing_id, getattr(package, "code", None),
                listing.boost_expires_at)
    return listing

