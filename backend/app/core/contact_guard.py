"""
app/core/contact_guard.py
Detects and masks phone numbers embedded in free text (listing descriptions).

Landlords often paste "Call/WhatsApp 097..." into the description, which
bypasses the contact paywall. We detect those for Trust and Safety review and
mask them on output when the viewer has not paid.

The original text is never modified in the database. Masking happens only in
the API response.
"""
import re

# Zambian mobile numbers: +260 / 260 / 0 prefix, then 7x or 9x, then 7 digits.
# Separators (space, dash, dot) tolerated. Validated against real listings.
_PHONE = re.compile(
    r"(?:\+?260[\s\-\.]?|0)"      # country code or leading zero
    r"[79]\d"                      # 76/77/79/95/96/97 style prefixes
    r"[\s\-\.]?\d{3}"
    r"[\s\-\.]?\d{3,4}"
)

MASK = "[contact hidden - get Verified Access to see it]"


def find_numbers(text):
    """Return a list of phone-like strings found in the text."""
    if not text:
        return []
    return [m.group(0) for m in _PHONE.finditer(text)]


def has_number(text):
    """True if the text appears to contain a phone number."""
    return bool(find_numbers(text))


def mask_numbers(text, replacement=MASK):
    """Return the text with any phone-like strings replaced."""
    if not text:
        return text
    return _PHONE.sub(replacement, text)
