"""
SupportTicket — a support request submitted from the Help Center.

Public users create a ticket (POST /support/tickets) and can later look up its
status by the short public ticket_id (GET /support/tickets/{ticket_id}). Admins
work tickets from the support area and can add a resolution note.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)

    ticket_id  = Column(String, unique=True, index=True, nullable=False)  # public code e.g. FMN-T-3F9A2C

    user_type  = Column(String, nullable=True)   # student | landlord
    category   = Column(String, nullable=True)   # connect | assist | payment | general
    reference_id = Column(String, nullable=True) # optional listing/transaction ref
    subject    = Column(String, nullable=False)
    message    = Column(Text, nullable=False)
    email      = Column(String, nullable=True)    # so support can reply

    status     = Column(String, nullable=False, default="new", index=True)  # new | in_progress | resolved | closed
    resolution_note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
