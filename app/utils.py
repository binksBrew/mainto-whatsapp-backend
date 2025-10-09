# app/utils.py
def normalize_phone(phone: str) -> str:
    """
    Normalize phone numbers to digits only (removes +, spaces, etc.)
    """
    if not phone:
        return ""
    return "".join([c for c in str(phone) if c.isdigit()])
