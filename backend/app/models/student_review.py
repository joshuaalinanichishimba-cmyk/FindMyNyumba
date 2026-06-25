"""
app/models/student_review.py
A rating + written comment a LANDLORD leaves on a STUDENT, after a completed
viewing. This is the second half of two-way reputation (the first half being
property reviews students leave on listings).

Gated in the endpoint on a COMPLETED viewing between this landlord and student,
so every student review traces back to a real, code-verified, in-person visit.
Reviews start 'pending' and are moderated like property reviews.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class StudentReview(Base):
    __tablename__ = "student_reviews"
    __table_args__ = {"extend_existing": True}

    id            = Column(Integer, primary_key=True, index=True)
    student_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)   # the reviewed student
    landlord_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)   # the reviewing landlord
    viewing_id    = Column(Integer, ForeignKey("viewing_requests.id"), nullable=True, index=True)
    landlord_name = Column(String)                       # snapshot of reviewer name at submit time
    rating        = Column(Integer, nullable=False)      # 1..5 (validated in the endpoint)
    comment       = Column(Text)
    status        = Column(String, nullable=False, default="pending", index=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
