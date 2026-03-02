from sqlalchemy import Column, Integer, String, Float
from db.session import Base

class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    location = Column(String, index=True)
    property_type = Column(String, index=True)
    price = Column(Float, index=True)
    owner_id = Column(Integer, index=True)
