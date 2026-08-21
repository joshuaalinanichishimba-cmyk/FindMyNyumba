"""
app/services/lenco_service.py
Lenco (BroadPay) payment gateway client - mobile money collections for Zambia.

SECURITY NOTES
- The secret key is read from Pydantic settings only. It is never logged, never
  echoed into an exception message, and never returned in an API response.
- LencoError messages are STUDENT SAFE. Raw provider text and HTTP bodies go to
  the logger, never to the caller.
- Card collections are deliberately absent. Lenco's /collections/card endpoint
  handles raw cardholder PII and requires PCI DSS certification which
  FindMyNyumba does not hold. Cards must go through Lenco hosted checkout.

HTTP CLIENT
Uses `requests` (already a project dependency) with explicit (connect, read)
timeouts. The codebase is synchronous end to end, including SQLAlchemy, so an
async client here would only introduce blocking calls inside async handlers.
"""
import hashlib
import hmac
import logging
import re
import time

import requests

from app.core.config import settings

logger = logging.getLogger("fmn.payments")

BASE_URL = "https://api.lenco.co/access/v2"

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

# Zambian mobile: 095/096/097 and 075/076/077, ten digits in local form.
ZM_MSISDN_RE = re.compile(r"^(?:0|\+?260)([79][5-7]\d{7})$")

_PREFIX_OPERATOR = {
    "96": "mtn",    "76": "mtn",
    "97": "airtel", "77": "airtel",
    "95": "zamtel", "75": "zamtel",
}

VALID_OPERATORS = ("airtel", "mtn", "zamtel")


class LencoError(Exception):
    """Student safe error. Never contains provider internals or secrets."""


class LencoConfigError(LencoError):
    """Raised when the integration is not configured. Should page an operator."""


def mask_phone(msisdn) -> str:
    """0971234727 -> 097***4727. Used for every log line touching a number."""
    digits = "".join(ch for ch in str(msisdn or "") if ch.isdigit())
    if len(digits) < 7:
        return "***"
    return digits[:3] + "***" + digits[-4:]


def _secret_key() -> str:
    key = getattr(settings, "LENCO_SECRET_KEY", None) or ""
    if not key.strip():
        logger.critical("LENCO_SECRET_KEY is not configured; payments cannot run.")
        raise LencoConfigError("Payments are temporarily unavailable.")
    return key.strip()


def _headers() -> dict:
    return {
        "Authorization": "Bearer " + _secret_key(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def normalize_phone(msisdn: str) -> str:
    """
    Accepts 0971234727, 971234727, 260971234727, +260971234727.
    Returns the local ten digit form 0971234727. Raises LencoError otherwise.
    """
    raw = "".join(str(msisdn or "").split())
    m = ZM_MSISDN_RE.match(raw)
    if not m:
        raise LencoError("Enter a valid Airtel, MTN or Zamtel number, for example 0971234567.")
    return "0" + m.group(1)


def detect_operator(msisdn: str) -> str:
    local = normalize_phone(msisdn)
    op = _PREFIX_OPERATOR.get(local[1:3])
    if not op:
        raise LencoError("That number is not a recognised Airtel, MTN or Zamtel line.")
    return op


def _friendly_http_error(status_code: int) -> str:
    if status_code in (401, 403):
        logger.critical("Lenco rejected our credentials (HTTP %s). Check LENCO_SECRET_KEY.", status_code)
        return "Payments are temporarily unavailable. Please try again shortly."
    if status_code == 429:
        return "Too many payment attempts right now. Please wait a moment and try again."
    if 400 <= status_code < 500:
        return "That payment request was declined. Check your number and try again."
    return "Payment network temporarily unavailable. Please try again."


def _parse(resp, reference: str) -> dict:
    try:
        body = resp.json()
    except ValueError:
        logger.error("Lenco non JSON response ref=%s http=%s body=%.300s",
                     reference, resp.status_code, resp.text)
        raise LencoError("Payment network temporarily unavailable. Please try again.")

    if resp.status_code >= 400 or not body.get("status"):
        logger.error("Lenco error ref=%s http=%s message=%s",
                     reference, resp.status_code, body.get("message"))
        raise LencoError(_friendly_http_error(resp.status_code))

    return body.get("data") or {}


def collect_mobile_money(amount, msisdn: str, reference: str,
                         operator: str = None, country: str = "zm",
                         bearer: str = "merchant") -> dict:
    """
    POST /collections/mobile-money

    NOT retried on network error. A timeout does not mean the request failed to
    reach Lenco, and a blind retry can trigger a second USSD prompt and double
    charge the student. On timeout we raise and let the status poll or webhook
    settle the true outcome.
    """
    phone = normalize_phone(msisdn)
    op = (operator or detect_operator(phone)).lower()
    if op not in VALID_OPERATORS:
        raise LencoError("Unsupported mobile money operator.")

    payload = {
        "amount": float(amount),
        "reference": reference,
        "phone": phone,
        "operator": op,
        "country": country,
        "bearer": bearer,
    }

    logger.info("collection.initiate ref=%s amount=%s operator=%s phone=%s",
                reference, amount, op, mask_phone(phone))

    try:
        r = requests.post(BASE_URL + "/collections/mobile-money",
                          json=payload, headers=_headers(), timeout=TIMEOUT)
    except requests.Timeout:
        logger.error("collection.timeout ref=%s phone=%s OUTCOME UNKNOWN, reconcile via status",
                     reference, mask_phone(phone))
        raise LencoError("The payment network is slow right now. "
                         "Check your phone before trying again.")
    except requests.RequestException:
        logger.exception("collection.unreachable ref=%s", reference)
        raise LencoError("Payment network temporarily unavailable. Please try again.")

    data = _parse(r, reference)
    logger.info("collection.accepted ref=%s lencoRef=%s status=%s",
                reference, data.get("lencoReference"), data.get("status"))
    return data


def get_collection_status(reference: str, attempts: int = 2) -> dict:
    """
    GET /collections/status/{reference}
    Read only and idempotent, so a short retry is safe here.
    """
    last = None
    for i in range(max(1, attempts)):
        try:
            r = requests.get(BASE_URL + "/collections/status/" + reference,
                             headers=_headers(), timeout=TIMEOUT)
            return _parse(r, reference)
        except LencoConfigError:
            raise
        except (requests.Timeout, requests.RequestException) as e:
            last = e
            if i + 1 < attempts:
                time.sleep(0.75 * (i + 1))
        except LencoError:
            raise
    logger.error("status.unreachable ref=%s err=%s", reference, type(last).__name__)
    raise LencoError("Could not confirm payment status. Please try again shortly.")


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """
    Lenco signs events with X-Lenco-Signature: HMAC SHA512 of the RAW request
    body, keyed by webhook_hash_key = sha256(API secret key) as a hex string.

    raw_body MUST be the exact bytes received. Re serialising the parsed JSON
    changes whitespace and key order and will never match.
    """
    if not signature:
        return False
    try:
        hash_key = hashlib.sha256(_secret_key().encode("utf-8")).hexdigest()
    except LencoConfigError:
        return False
    expected = hmac.new(hash_key.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature.strip())
