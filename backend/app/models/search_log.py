"""
SearchLog model - anonymous search analytics.

Records what students search for (query text, university filter, price range)
WITHOUT any user_id, so analytics are aggregate-only ("most searched university")
and never tie a search to an individual. Fire-and-forget logged from browse.
"""
from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class SearchLog(Base):
    __tablename__ = "search_logs"
    __table_args__ = {"extend_existing": True}

    id            = Column(BigInteger, primary_key=True, index=True)
    query         = Column(String, nullable=True, index=True)
    university    = Column(String, nullable=True, index=True)
    min_price     = Column(Float, nullable=True)
    max_price     = Column(Float, nullable=True)
    results_count = Column(Integer, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), index=True)
