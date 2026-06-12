"""
app/core/audit.py
One-call helper for writing AuditLog entries.

WHY THIS EXISTS
---------------
The AuditLog model already exists but is written in exactly one place out of
~50 admin endpoints. The moment money, suspensions, refunds or disputes are
involved, "who did this and when" becomes a legal/operational question, not a
curiosity. This helper makes adding a tamper-evident trail a single line, so
there's no excuse to skip it.

USAGE
-----
    from app.core.audit import record_audit

    @router.post("/users/{user_id}/suspend")
    def suspend_user(user_id: int, request: Request,
                     admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
        ...                                   # do the work
        record_audit(
            db, request, actor=admin,
            action="user.suspend",
            entity_type="user", entity_id=user_id,
            meta={"reason": "policy violation"},
        )
        return {...}

Design notes:
  - `meta` accepts a dict and is stored as JSON text.
  - The function commits its own row only if `commit=True` (default). If you're
    already inside a transaction you want to keep atomic with the audit row,
    pass commit=False and commit once at the end of the endpoint.
  - It NEVER raises. An audit-write failure must not break the actual admin
    action; failures are logged and swallowed.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.admin_models import AuditLog

log = logging.getLogger("findmynyumba.audit")


def record_audit(
    db: Session,
    request: Optional[Request],
    *,
    actor: Any = None,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Any = None,
    meta: Optional[dict] = None,
    commit: bool = True,
) -> None:
    """Write a single audit row. Best-effort: never raises to the caller."""
    try:
        ip = None
        ua = None
        if request is not None:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")

        entry = AuditLog(
            actor_id=getattr(actor, "id", None),
            actor_role=getattr(actor, "role", None),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip_address=ip,
            user_agent=ua,
            meta=json.dumps(meta) if meta is not None else None,
        )
        db.add(entry)
        if commit:
            db.commit()
    except Exception as exc:  # pragma: no cover - audit must never break the action
        log.warning("audit write failed for action=%s: %s", action, exc)
        try:
            db.rollback()
        except Exception:
            pass
