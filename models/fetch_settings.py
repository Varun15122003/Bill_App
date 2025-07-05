from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from models.base import Base

class FetchSettings(Base):
    __tablename__ = "fetch_settings"
    id = Column(Integer, primary_key=True, index=True)
    bills_fetch_count = Column(Integer, default=3)  # Default to 3 for bills
    customers_fetch_count = Column(Integer, default=5)  # Default to 5 for customers
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())