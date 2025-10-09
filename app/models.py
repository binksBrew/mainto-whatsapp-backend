# app/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # landlord settings
    vendor_id = Column(String(255), nullable=True)         # Cashfree vendor/sub-merchant id
    google_sheet_url = Column(String(2048), nullable=True) # link to sheet
    daily_penalty = Column(Float, default=50.0)            # per-day penalty default
    
    reminder_time_1 = Column(String(5), default="10:00")
    reminder_time_2 = Column(String(5), default="18:00")
    
    phone_number = Column(String(20), nullable=True)
    manager_phone = Column(String(20), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
