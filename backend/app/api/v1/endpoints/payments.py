"""
app/api/v1/endpoints/payments.py
Verified Access payments via MTN MoMo. The frontend (pay-verified-access.html)
calls initiate + status. Amount is server-set from the tier; never trust client.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User
from app.models.admin_models import Transaction
from app.services import momo_service

router = APIRouter(prefix="/payments", tags=["payments"])

TIER_PRICES = {
    "student_connect": settings.TIER_STUDENT_CONNECT_ZMW,
    "assisted_move":   settings.TIER_ASSISTED_MOVE_ZMW,
    "escort_assist":   settings.TIER_ESCORT_ASSIST_ZMW,
}
TIER_LABELS = {
    "student_connect": "Student Connect",
    "assisted_move":   "Assisted Move",
    "escort_assist":   "Escort Assist",
}


class InitiateBody(BaseModel):
    msisdn: str
    tier: str = "student_connect"


@router.post("/verified-access/initiate")
def initiate(body: InitiateBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tier = body.tier if body.tier in TIER_PRICES else "student_connect"
    price = TIER_PRICES[tier]          # server-authoritative price
    label = TIER_LABELS[tier]

    ref = "FMN-" + uuid.uuid4().hex[:12].upper()
    txn = Transaction(
        ref=ref,
        user_id=current_user.id,
        type="verification_fee",
        amount=price,
        currency=settings.MOMO_CURRENCY,   # EUR in sandbox, ZMW in prod
        method="mtn_money",
        status="pending",
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    try:
        momo_ref = momo_service.request_to_pay(
            amount=price,
            msisdn=body.msisdn,
            external_id=ref,
            payer_message="FindMyNyumba Verified Access",
            payee_note=label,
        )
        txn.momo_ref_id = momo_ref
        db.commit()
    except Exception as e:
        txn.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail="Could not reach payment provider. Please try again.")

    return {"transaction_id": txn.id, "ref": ref, "status": "pending", "tier": tier, "amount_display": f"{settings.MOMO_CURRENCY} {int(price)}.00"}


@router.get("/{payment_id}/status")
def status(payment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == payment_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if txn.user_id != current_user.id and getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Not your transaction.")

    # Already finalized
    if txn.status in ("success", "failed"):
        return {"status": "success" if txn.status == "success" else "failed", "ref": txn.ref}

    if not txn.momo_ref_id:
        return {"status": "pending", "ref": txn.ref}

    try:
        momo_status = momo_service.check_status(txn.momo_ref_id)
    except Exception:
        return {"status": "pending", "ref": txn.ref}

    if momo_status == "SUCCESSFUL":
        txn.status = "success"
        txn.provider_ref = txn.momo_ref_id
        db.commit()
        return {"status": "success", "ref": txn.ref}
    if momo_status == "FAILED":
        txn.status = "failed"
        db.commit()
        return {"status": "failed", "ref": txn.ref}
    return {"status": "pending", "ref": txn.ref}
