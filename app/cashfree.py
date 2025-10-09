import httpx
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("CASHFREE_APP_ID")
SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY")
BASE_URL = "https://sandbox.cashfree.com/pg/links"
PLATFORM_FEE_PERCENT = float(os.getenv("PLATFORM_FEE_PERCENT", "3"))

# ✅ Debugging: warn if credentials are missing
if not APP_ID or not SECRET_KEY:
    print("[Cashfree] ⚠️ APP_ID or SECRET_KEY not found! Check your .env file and environment variables.")
else:
    print(f"[Cashfree] ✅ APP_ID loaded: {APP_ID[:6]}... (masked)")

async def create_payment_link(amount, customer_name, customer_phone, customer_email="test@example.com"):
    try:
        base_amount = float(amount)
    except (ValueError, TypeError):
        print("[Cashfree] Invalid amount:", amount)
        base_amount = 0.0

    total_amount = round(base_amount + (base_amount * PLATFORM_FEE_PERCENT / 100), 2)

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "x-client-id": APP_ID or "",    # ✅ avoid None
        "x-client-secret": SECRET_KEY or "",
        "x-api-version": "2022-09-01"
    }

    print("[Cashfree] Headers:", headers)  # ✅ Debug print
    payload = {
        "link_amount": total_amount,
        "link_currency": "INR",
        "link_purpose": f"Payment for {customer_name}",
        "customer_details": {
            "customer_phone": str(customer_phone),
            "customer_email": customer_email,
            "customer_name": customer_name
        },
        "link_notify": {
            "send_sms": True,
            "send_email": False
        }
    }

    print(
        f"[Cashfree] Creating hosted payment link for: {customer_name} | "
        f"Base: {base_amount} | +{PLATFORM_FEE_PERCENT}% fee => {total_amount}"
    )

    async with httpx.AsyncClient() as client:
        r = await client.post(BASE_URL, headers=headers, json=payload)
        print("[Cashfree] Status:", r.status_code)
        print("[Cashfree] Response:", r.text)
        r.raise_for_status()
        return r.json()

def create_payment_link_sync(amount, customer_name, customer_phone, customer_email="test@example.com"):
    try:
        return asyncio.run(create_payment_link(amount, customer_name, customer_phone, customer_email))
    except Exception as e:
        print(f"[Cashfree] Sync wrapper failed: {e}")
        return None
