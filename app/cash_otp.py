import random, time
from typing import Dict

# Simple in-memory OTP store (phone -> (otp, expiry))
_OTP_STORE: Dict[str, tuple] = {}

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def _normalize(phone: str) -> str:
    return "".join(c for c in str(phone) if c.isdigit())

def set_otp(phone: str, otp: str, ttl: int = 300):
    phone = _normalize(phone)
    expire_at = time.time() + ttl
    _OTP_STORE[phone] = (otp, expire_at)

def verify_otp(phone: str, otp: str) -> bool:
    phone = _normalize(phone)
    data = _OTP_STORE.get(phone)
    if not data:
        return False
    code, expire_at = data
    if time.time() > expire_at:
        _OTP_STORE.pop(phone, None)
        return False
    if code == otp:
        _OTP_STORE.pop(phone, None)
        return True
    return False
