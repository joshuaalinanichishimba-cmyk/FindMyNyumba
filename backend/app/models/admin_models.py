"""
app/models/admin_models.py

New tables that power the admin platform's financial, audit, and operational
modules. Kept in one file for a clean drop-in; split later if you prefer
one-model-per-file like the rest of the codebase.

Conventions match the existing models:
  - Integer primary keys, FKs to users.id / listings.id
  - Base from app.core.database
  - extend_existing so repeated imports don't error
  - String status columns (portable across SQLite dev + Postgres/Supabase prod)
  - server_default=func.now() timestamps

After adding this file, register the models before create_all (see main.py
patch in the wiring notes). Base.metadata.create_all then creates the tables
on next startup — no Alembic migration needed for the dev cycle.
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, DateTime, Text,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.core.database import Base


# ── Transactions ──────────────────────────────────────────────────────────────
class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, index=True)
    ref         = Column(String, unique=True, index=True)        # 'TXN-000123'
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=True, index=True)

    # verification_fee | featured | boost | escrow_deposit | viewing_fee
    type        = Column(String, nullable=False, index=True)
    amount      = Column(Float,  nullable=False)
    currency    = Column(String, nullable=False, default="ZMW")

    # airtel_money | mtn_money | zamtel_money | bank_transfer
    method      = Column(String, nullable=False)
    # pending | success | failed | refunded
    status      = Column(String, nullable=False, default="pending", index=True)
    provider_ref = Column(String, nullable=True)                 # mobile-money/bank ref

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Escrow ────────────────────────────────────────────────────────────────────
class Escrow(Base):
    __tablename__ = "escrow"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, index=True)
    ref         = Column(String, unique=True, index=True)
    txn_id      = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    student_id  = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    landlord_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)

    amount      = Column(Float, nullable=False)
    # waiting | held | released | refunded | disputed
    status      = Column(String, nullable=False, default="waiting", index=True)
    dispute_reason = Column(Text, nullable=True)

    held_at     = Column(DateTime(timezone=True), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


# ── Institutions ──────────────────────────────────────────────────────────────
class Institution(Base):
    __tablename__ = "institutions"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False, index=True)
    town       = Column(String, nullable=True)
    type       = Column(String, nullable=True)         # university | college | TEVET
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Notifications ─────────────────────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"extend_existing": True}

    id        = Column(Integer, primary_key=True, index=True)
    # null user_id = broadcast (visible to all admins)
    user_id   = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    type      = Column(String, nullable=False)         # report | verification | payment | escrow | listing
    title     = Column(String, nullable=False)
    body      = Column(Text, nullable=True)
    channel   = Column(String, nullable=False, default="in_app")  # in_app | email | sms
    read_at   = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Audit log (append-only by convention; revoke UPDATE/DELETE in prod) ────────
class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"extend_existing": True}

    id          = Column(BigInteger, primary_key=True, index=True)
    actor_id    = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_role  = Column(String, nullable=True)
    action      = Column(String, nullable=False, index=True)   # 'listing.approve'
    entity_type = Column(String, nullable=True, index=True)    # 'listing'
    entity_id   = Column(String, nullable=True, index=True)
    ip_address  = Column(String, nullable=True)
    user_agent  = Column(String, nullable=True)
    meta        = Column(Text, nullable=True)                  # JSON string
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


# ── Internal admin notes on a listing ──────────────────────────────────────────
class AdminNote(Base):
    __tablename__ = "admin_notes"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    author_id  = Column(Integer, ForeignKey("users.id"), nullable=True)
    text       = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── RBAC: one row per (role, permission) ────────────────────────────────────────
class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, index=True)
    role       = Column(String, nullable=False, index=True)
    permission = Column(String, nullable=False, index=True)
