"""
app/services/moneyunify_service.py
MoneyUnify aggregator: collect via MTN, Airtel, Zamtel through one API.
Docs: https://owk7kqf8sn.apidog.io/  |  https://github.com/blessedjasonmwanza/MoneyUnify
auth_id from settings.MONEYUNIFY_AUTH_ID (kept secret in env).
"""
import requests
from app.core.config import settings


def _base():
    return settings.MONEYUNIFY_BASE_URL.rstrip("/")


def request_payment(amount, from_payer):
    """
    Prompt the payer's phone for approval. Returns the MoneyUnify transaction_id.
    from_payer: local number, e.g. '0971234567' or '260971234567'.
    """
    r = requests.post(
        f"{_base()}/payments/request",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        data={"from_payer": from_payer, "amount": str(int(amount)), "auth_id": settings.MONEYUNIFY_AUTH_ID},
        timeout=40,
    )
    j = r.json()
    if r.status_code >= 400 or j.get("isError"):
        raise RuntimeError(f"request_payment failed: {r.status_code} {j.get('message')}")
    return j["data"]["transaction_id"]


def verify_payment(transaction_id):
    """
    Check a payment's status. Returns one of MoneyUnify's status strings,
    normalised to: 'successful', 'pending', 'failed'.
    """
    r = requests.post(
        f"{_base()}/payments/verify",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        data={"transaction_id": transaction_id, "auth_id": settings.MONEYUNIFY_AUTH_ID},
        timeout=40,
    )
    j = r.json()
    status = (j.get("data") or {}).get("status", "").lower()
    if status in ("successful", "success", "completed"):
        return "successful"
    if status in ("failed", "cancelled", "canceled", "declined", "rejected"):
        return "failed"
    return "pending"   # initiated, otp-pending, processing, etc.
