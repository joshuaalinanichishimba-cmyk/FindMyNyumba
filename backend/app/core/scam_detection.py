"""
app/core/scam_detection.py
Lightweight, dependency-free scam signal scanner for chat messages.

WHY THIS EXISTS
---------------
The dominant scam in Zambian student housing is "pay a deposit before viewing,
sent to a personal mobile-money number." That conversation happens inside
FindMyNyumba's own chat, which is exactly where Facebook Marketplace can't see
it — so this is a structural advantage worth using.

This module does NOT block messages. It returns a list of human-readable
signal strings so the message can still be delivered while being flagged for
admin review. Blocking outright would (a) generate false positives that frustrate
honest users and (b) push the bad actors to be more careful. Flagging lets you
collect data on real patterns first, then tighten later.

It is deliberately:
  - regex/string only (no ML, no network calls, no new dependencies)
  - cheap enough to run on every outbound message
  - conservative: a signal means "worth a human glance," not "this is a scam"

USAGE
-----
    from app.core.scam_detection import scan_message

    signals = scan_message(content)
    if signals:
        # persist signals (e.g. on the Message row or an admin queue) and/or
        # write an audit/notification entry. Do NOT raise — deliver the message.
        ...
"""
from __future__ import annotations

import re
from typing import List

# --- Zambian mobile money number patterns --------------------------------
# Airtel/MTN/Zamtel numbers are 09x / 07x (10 digits) or +260 / 260 prefixed.
# We tolerate spaces, dashes and dots between digit groups, which is how people
# actually paste numbers in chat.
_PHONE_PATTERNS = [
    re.compile(r"(?:\+?260|0)\s*[7-9]\d(?:[\s.\-]?\d){7}"),
]

# --- Off-platform-payment / pay-before-viewing language -------------------
# Each tuple is (compiled_regex, signal_label). Labels are what the admin sees.
_KEYWORD_RULES = [
    (re.compile(r"\bdeposit\b.*\b(before|first|now|today)\b", re.I),
     "asks for deposit before viewing"),
    (re.compile(r"\b(send|pay|transfer)\b.*\b(money|cash|deposit|fee|funds?)\b", re.I),
     "requests money transfer"),
    (re.compile(r"\b(airtel|mtn|zamtel)\s*(money|momo|mobile\s*money)\b", re.I),
     "names a mobile money service"),
    (re.compile(r"\bmomo\b", re.I),
     "mentions MoMo"),
    (re.compile(r"\b(reserve|secure|hold)\b.*\b(room|place|spot|unit)\b.*\b(pay|deposit|fee|money)\b", re.I),
     "pay-to-reserve pressure"),
    (re.compile(r"\b(western\s*union|world\s*remit|moneygram)\b", re.I),
     "names an external money-transfer service"),
    (re.compile(r"\b(whats\s*app|whatsapp|call me on|text me on|reach me on)\b", re.I),
     "pushes conversation off-platform"),
    (re.compile(r"\b(no|cannot|can't)\b.*\b(view|viewing|visit|see the (room|place))\b", re.I),
     "discourages viewing"),
    (re.compile(r"\b(i am|i'm|currently)\b.*\b(abroad|overseas|out of (town|the country)|another (city|town))\b", re.I),
     "classic 'I'm away, just send money' setup"),
]


def scan_message(content: str) -> List[str]:
    """
    Return a list of distinct scam-signal labels found in `content`.
    Empty list means nothing matched. Never raises.
    """
    if not content or not isinstance(content, str):
        return []

    signals: List[str] = []

    # Phone numbers shared in chat are the single strongest signal for the
    # deposit-redirection scam, so they get their own label.
    for pat in _PHONE_PATTERNS:
        if pat.search(content):
            signals.append("shares a phone/mobile-money number in chat")
            break

    for pattern, label in _KEYWORD_RULES:
        if pattern.search(content):
            signals.append(label)

    # De-dupe while preserving order.
    seen = set()
    unique = []
    for s in signals:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def risk_score(signals: List[str]) -> int:
    """
    Convenience: turn a signal list into a coarse 0-100 score for sorting an
    admin queue. Sharing a number + asking for a deposit is the high-risk combo.
    """
    if not signals:
        return 0
    score = min(100, 25 * len(signals))
    if "shares a phone/mobile-money number in chat" in signals:
        score = min(100, score + 25)
    return score
