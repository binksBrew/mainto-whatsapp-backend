# app/schemas.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# ---------- auth ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ---------- user ----------
class UserOut(BaseModel):
    id: int
    email: EmailStr
    vendor_id: Optional[str] = None
    google_sheet_url: Optional[str] = None
    daily_penalty: float
    platform_fee_percent: float

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    vendor_id: Optional[str] = None
    google_sheet_url: Optional[str] = None
    daily_penalty: float = 50.0
    platform_fee_percent: float = 3.0

class UserSettingsUpdate(BaseModel):
    vendor_id: Optional[str] = None
    google_sheet_url: Optional[str] = None
    daily_penalty: Optional[float] = Field(None, ge=0)
    platform_fee_percent: Optional[float] = Field(None, ge=0, le=100)
