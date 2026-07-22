"""
app/services/momo_service.py
MTN MoMo Collections service: token, request-to-pay, status polling.
"""
import base64
import uuid
import requests
from app.core.config import settings


def _base():
    return settings.MOMO_BASE_URL.rstrip("/")


def get_token():
    auth = base64.b64encode(f"{settings.MOMO_API_USER}:{settings.MOMO_API_KEY}".encode()).decode()
    r = requests.post(
        f"{_base()}/collection/token/",
        headers={"Authorization": f"Basic {auth}", "Ocp-Apim-Subscription-Key": settings.MOMO_SUBSCRIPTION_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def request_to_pay(amount, msisdn, external_id, payer_message="FindMyNyumba Verified Access", payee_note="Verified Access"):
    token = get_token()
    ref = str(uuid.uuid4())
    body = {
        "amount": str(int(amount)),
        "currency": settings.MOMO_CURRENCY,
        "externalId": external_id,
        "payer": {"partyIdType": "MSISDN", "partyId": msisdn},
        "payerMessage": payer_message,
        "payeeNote": payee_note,
    }
    r = requests.post(
        f"{_base()}/collection/v1_0/requesttopay",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": ref,
            "X-Target-Environment": settings.MOMO_TARGET_ENV,
            "Ocp-Apim-Subscription-Key": settings.MOMO_SUBSCRIPTION_KEY,
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    if r.status_code != 202:
        raise RuntimeError(f"request_to_pay failed: {r.status_code} {r.text}")
    return ref


def check_status(ref):
    token = get_token()
    r = requests.get(
        f"{_base()}/collection/v1_0/requesttopay/{ref}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": settings.MOMO_TARGET_ENV,
            "Ocp-Apim-Subscription-Key": settings.MOMO_SUBSCRIPTION_KEY,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("status", "PENDING")
