import httpx
import os
import asyncio

# 🔹 Load credentials from environment
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

if not ACCESS_TOKEN or not WHATSAPP_PHONE_ID:
    print("[WhatsApp] ⚠️ Missing WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_ID. Check your .env file.")

#  Helper to extract just the Cashfree link ID
def extract_link_code(full_url: str) -> str:
    """
    Extract only the unique payment link code from Cashfree URL.
    e.g. https://payments-test.cashfree.com/links/T99bf1pnncmg → T99bf1pnncmg
    """
    if not full_url:
        return ""
    return full_url.rstrip("/").split("/")[-1]


#  Async: BEFORE DUE DATE reminder
async def send_rent_reminder_before_due_mainto_2(name, due_date, penalty_amount, pay_link, to):
    """
    WhatsApp template: rent_reminder_before_due
    Body variables:
        {{1}} = Tenant name
        {{2}} = Due date
        {{3}} = Penalty per day
    Button:
        {{1}} = Payment link code (dynamic part of URL)
    """
    link_code = extract_link_code(pay_link)
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": str(to),
        "type": "template",
        "template": {
            "name": "rent_reminder_before_due_mainto_2",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(name)},       # {{1}}
                        {"type": "text", "text": str(due_date)},   # {{2}}
                        {"type": "text", "text": str(penalty_amount)}  # {{3}}
                    ]
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [
                        {"type": "text", "text": link_code}        # fills {{1}} in the URL
                    ]
                }
            ]
        }
    }

    print(f"[WhatsApp] BEFORE DUE | {to} | {name} | {due_date} | Penalty: {penalty_amount} | {link_code}")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=data)
        print(f"[WhatsApp] Status: {r.status_code}, Response: {r.text}")
        return r.status_code, r.text


# Async: AFTER DUE DATE reminder
async def send_rent_reminder_after_due_mainto_2(name, due_date, penalty_amount, pay_link, to):
    """
    WhatsApp template: rent_reminder_after_due_mainto_2
    Body variables:
        {{1}} = Tenant name
        {{2}} = Due date
        {{3}} = Penalty so far
    Button:
        {{1}} = Payment link code (dynamic part of URL)
    """
    link_code = extract_link_code(pay_link)
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": str(to),
        "type": "template",
        "template": {
            "name": "rent_reminder_after_due_mainto_2",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(name)},       # {{1}}
                        {"type": "text", "text": str(due_date)},   # {{2}}
                        {"type": "text", "text": str(penalty_amount)}  # {{3}}
                    ]
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [
                        {"type": "text", "text": link_code}        # fills {{1}} in the URL
                    ]
                }
            ]
        }
    }

    print(f"[WhatsApp] AFTER DUE | {to} | {name} | {due_date} | Penalty: {penalty_amount} | {link_code}")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=data)
        print(f"[WhatsApp] Status: {r.status_code}, Response: {r.text}")
        return r.status_code, r.text


# Sync wrappers
def send_rent_reminder_before_due_sync(name, due_date, penalty_amount, pay_link, to):
    try:
        return asyncio.run(send_rent_reminder_before_due_mainto_2(name, due_date, penalty_amount, pay_link, to))
    except Exception as e:
        print(f"[WhatsApp] BEFORE DUE Sync failed: {e}")
        return 500, str(e)

def send_rent_reminder_after_due_sync(name, due_date, penalty_amount, pay_link, to):
    try:
        return asyncio.run(send_rent_reminder_after_due_mainto_2(name, due_date, penalty_amount, pay_link, to))
    except Exception as e:
        print(f"[WhatsApp] AFTER DUE Sync failed: {e}")
        return 500, str(e)


# OTP message (Authentication template)
async def send_otp(to: str, otp: str):
    """
    Sends OTP using the approved authentication template: `rent_cash_otp_mainto`
    Template must have:
        {{1}} = OTP code
    """
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": "rent_cash_otp_mainto",   # <-- your approved Authentication template name
            "language": {"code": "en_US"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": otp}   # fills {{1}}
                    ]
                }
            ]
        }
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
        print(f"[WhatsApp] OTP send status: {r.status_code} {r.text}")
        return r.status_code, r.text


# Simple Text Message (fallback)
async def send_message(to: str, text: str):
    """
    Sends a simple text message (non-template).
    Use for debugging / internal messages, not for OTP.
    """
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
        print(f"[WhatsApp] Msg status: {r.status_code} {r.text}")
        return r.status_code, r.text
