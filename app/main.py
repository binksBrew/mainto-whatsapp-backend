import os
import tempfile
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request, HTTPException, Depends
from app import sheets, cashfree, whatsapp, models, cash_otp, db
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel
from app.models import User
from app.db import get_db, SessionLocal
from app.auth import get_current_user
from fastapi.middleware.cors import CORSMiddleware
from app.auth import router as auth_router
from datetime import datetime, date, timedelta
from app import cashfree, whatsapp, sheets,cash_otp, models
from app.cashfree import PLATFORM_FEE_PERCENT
from app import models
from app.utils import normalize_phone
from fastapi import Request, Response
from app.auth import get_current_user
from sqlalchemy.orm import Session
from collections import defaultdict

app = FastAPI()

load_dotenv()  # ✅ Load env FIRST

app = FastAPI()
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "myverifytoken123")

origins = [
    "http://localhost:5173",         # for local dev
    "http://127.0.0.1:5173",         # alternate local
    "http://<your-frontend-domain>", # if you use a domain
    "http://3.237.193.244",   # your frontend public IP
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down later: ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# ---- Configurable platform fee ----
PLATFORM_FEE_PERCENT = float(os.getenv("PLATFORM_FEE_PERCENT", 3))  # default 3% if not set

# ---- Scheduler ----
scheduler = BackgroundScheduler()
scheduler.start()


# Helper: Send due reminders for a specific user (sync)
def send_due_for_user(user_id: int, sheet_url: str, daily_penalty: float):
    """
    Runs automatically by APScheduler for each landlord at their configured times.
    """
    print(f"[Scheduler] Sending reminders for user {user_id} ...")
    try:
        sheets.set_sheet_by_url(sheet_url)
        due_rows = sheets.get_due_rows(default_daily_penalty=daily_penalty)
        if not due_rows:
            print(f"[Scheduler] No due rows for user {user_id}")
            return

        for row in due_rows:
            base_amount = float(row.get("Amount", 0))
            new_penalty = float(row.get("new_penalty", row.get("Penalty", 0)) or 0)

            subtotal = base_amount + new_penalty
            fee = round(subtotal * (PLATFORM_FEE_PERCENT / 100), 2)
            total_to_charge = subtotal + fee

            # These must exist in app/cashfree.py and app/whatsapp.py
            payment = cashfree.create_payment_link_sync(
                amount=total_to_charge,
                customer_name=row.get("Name", ""),
                customer_phone=row.get("PhoneNumber", "")
            )
            if not payment:
                continue

            pay_link = payment.get("link_url")
            whatsapp.send_payment_reminder_sync(
                name=row.get("Name", ""),
                amount=total_to_charge,
                due_date=row.get("DueDate", ""),
                pay_link=pay_link,
                to=row.get("PhoneNumber", "")
            )

            sheets.update_penalty_and_reminders(row["_row_number"], new_penalty)

        print(f"[Scheduler] ✅ Finished reminders for user {user_id}")

    except Exception as e:
        print(f"[Scheduler] ⚠️ Error for user {user_id}: {e}")

def schedule_user_jobs(user: models.User):
    """
    Set up 2 cron jobs for a user based on their reminder times.
    Runs every time user updates settings OR app starts.
    """
    # Remove old jobs if any
    if scheduler.get_job(f"user-{user.id}-rem1"):
        scheduler.remove_job(f"user-{user.id}-rem1")
    if scheduler.get_job(f"user-{user.id}-rem2"):
        scheduler.remove_job(f"user-{user.id}-rem2")

    # Parse and schedule
    try:
        if user.reminder_time_1:
            h1, m1 = map(int, user.reminder_time_1.split(":"))
            scheduler.add_job(
                send_due_for_user,
                trigger=CronTrigger(hour=h1, minute=m1),
                args=[user.id, user.google_sheet_url, user.daily_penalty],
                id=f"user-{user.id}-rem1"
            )
    except Exception:
        print(f"[Scheduler] Invalid reminder_time_1 for user {user.id}")

    try:
        if user.reminder_time_2:
            h2, m2 = map(int, user.reminder_time_2.split(":"))
            scheduler.add_job(
                send_due_for_user,
                trigger=CronTrigger(hour=h2, minute=m2),
                args=[user.id, user.google_sheet_url, user.daily_penalty],
                id=f"user-{user.id}-rem2"
            )
    except Exception:
        print(f"[Scheduler] Invalid reminder_time_2 for user {user.id}")

    print(f"[Scheduler] ✅ Jobs scheduled for {user.email} at {user.reminder_time_1} & {user.reminder_time_2}")

@app.on_event("startup")
def on_startup():
    db = next(get_db())
    try:
        users = db.query(models.User).all()
        for u in users:
            if u.google_sheet_url:
                schedule_user_jobs(u)
        print(f"[Scheduler] ✅ Loaded {len(users)} users with reminder jobs.")
    finally:
        db.close()

# 0. Health check
@app.get("/")
def home():
    return {"status": "ok"}

# 📌 1. Upload local Excel for preview
@app.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    """
    Allows landlord to upload an Excel file and preview its contents (not saved).
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.write(await file.read())
    tmp.close()

    df = pd.read_excel(tmp.name)
    required = ["Name", "PhoneNumber", "Amount", "DueDate", "PaymentStatus", "Penalty", "NoOfReminders"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {"status": "error", "missing_columns": missing}

    preview = df.head(5).to_dict(orient="records")
    return {"status": "ok", "preview": preview, "row_count": len(df)}

# 2. Configure Landlord Settings (JSON body) — Saves in DB & schedules jobs
# 

class ConfigRequest(BaseModel):
    sheet_url: str
    penalty_amount: float
    reminder_time_1: str
    reminder_time_2: str | None = None
    phone_number: str
    manager_phone: str

@app.post("/configure-landlord")
async def configure_landlord(
    body: ConfigRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Creates or updates landlord configuration in the same User table.
    Ensures the sheet is reachable and re-schedules jobs.
    """

    try:
        # ✅ Validate Google Sheet access (to ensure URL is correct)
        sheets.set_sheet_by_url(body.sheet_url)

        # ✅ Update or create landlord configuration directly on User model
        current_user.google_sheet_url = body.sheet_url
        current_user.daily_penalty = body.penalty_amount
        current_user.reminder_time_1 = body.reminder_time_1
        current_user.reminder_time_2 = body.reminder_time_2
        current_user.phone_number = body.phone_number
        current_user.manager_phone = body.manager_phone

        db.commit()

        # Reschedule reminder jobs dynamically for this landlord
        schedule_user_jobs(current_user)

        # Optional WhatsApp confirmation (comment out if not ready)
        try:
            msg = (
                f"✅ Mainto Settings Updated Successfully!\n\n"
                f"📊 Sheet: {body.sheet_url}\n"
                f"💰 Penalty: ₹{body.penalty_amount}\n"
                f"🕒 Reminder 1: {body.reminder_time_1}\n"
                f"🕒 Reminder 2: {body.reminder_time_2 or '—'}"
            )
            await whatsapp.send_text(body.phone_number, msg)
        except Exception as wa_err:
            print(f"[WhatsApp Notify] Failed: {wa_err}")

        return {
            "status": "ok",
            "message": "Settings saved and reminder jobs scheduled successfully.",
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error saving settings: {str(e)}")


@app.get("/send-due")
async def send_due(current_user: models.User = Depends(get_current_user)):
    """
    Trigger reminder sending manually for the logged-in landlord.
    Decides which WhatsApp template to use (before due or after due).
    """
    # ---------------------------
    # 1. Load Google Sheet data
    # ---------------------------
    try:
        sheets.set_sheet_by_url(current_user.google_sheet_url)
        due_rows = sheets.get_due_rows(default_daily_penalty=current_user.daily_penalty)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if not due_rows:
        return {"status": "no_due_payments"}

    today = date.today()
    results = []

    # ---------------------------
    # 2. Process each tenant
    # ---------------------------
    for row in due_rows:
        base_amount = float(row.get("Amount", 0))
        new_penalty = float(row.get("new_penalty", row.get("Penalty", 0)) or 0)

        # calculate total amount
        subtotal = base_amount + new_penalty
        fee = round(subtotal * (PLATFORM_FEE_PERCENT / 100), 2)
        total_to_charge = subtotal + fee

        # parse due date safely
        due_str = row.get("DueDate", "")
        try:
            due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
        except Exception:
            due_date = None

        # ---------------------------
        # 3. Create payment link
        # ---------------------------
        payment = await cashfree.create_payment_link(
            amount=total_to_charge,
            customer_name=row.get("Name", ""),
            customer_phone=row.get("PhoneNumber", "")
        )
        pay_link = payment.get("link_url")

        # ---------------------------
        # 4. Decide which WhatsApp template to use
        # ---------------------------
        if due_date and today <= due_date:
            # Before or on due date
            penalty_per_day = float(row.get("PenaltyPerDay") or current_user.daily_penalty or 0)
            status, resp = await whatsapp.send_rent_reminder_before_due_mainto_2(
                name=row.get("Name", ""),
                due_date=due_str,
                penalty_amount=penalty_per_day,
                pay_link=pay_link,
                to=row.get("PhoneNumber", "")
            )
        else:
            # After due date — include penalty
            penalty_per_day = float(row.get("PenaltyPerDay") or current_user.daily_penalty or 0)
            status, resp = await whatsapp.send_rent_reminder_after_due_mainto_2(
                name=row.get("Name", ""),
                due_date=due_str,
                penalty_amount=penalty_per_day,
                pay_link=pay_link,
                to=row.get("PhoneNumber", "")
            )

        # ---------------------------
        # 5. Update penalty/reminder columns in Google Sheet
        # ---------------------------
        sheets.update_penalty_and_reminders(row["_row_number"], new_penalty)

        results.append({
            "row": row.get("_row_number"),
            "status": status,
            "response": resp,
            "final_amount": total_to_charge
        })

    return {"sent": results}




# ---------------------------
# Cashfree Webhook (unchanged)
# ---------------------------

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = "".join([c for c in str(phone) if c.isdigit()])
    # Remove leading country code duplicates like 9191...
    if digits.startswith("91") and len(digits) > 10:
        # Keep last 10 digits if it looks like a double-coded number
        return digits[-10:]
    return digits


@app.post("/cashfree-webhook")
async def cashfree_webhook(request: Request):
    payload = await request.json()
    print("[Cashfree Webhook] Received:", payload)

    event = payload.get("event") or payload.get("type")
    data = payload.get("data", {})

    if event in ["order.paid", "link.paid", "PAYMENT_SUCCESS_WEBHOOK"]:
        customer_id = normalize_phone(data.get("customer_details", {}).get("customer_phone"))
        transaction_id = (
            data.get("order_id")
            or data.get("cf_order_id")
            or data.get("order", {}).get("order_id")
        )
        receipt_url = (
            data.get("payment_link")
            or data.get("link_url")
            or f"https://merchant.cashfree.com/order/{transaction_id}"
        )

        rows = sheets.sheet.get_all_records()
        if not rows:
            print("[Webhook] No rows found in sheet.")
            return {"status": "no_rows"}

        headers = list(rows[0].keys()) if rows else []
        txn_col = headers.index("TransactionID") + 1 if "TransactionID" in headers else None
        receipt_col = headers.index("ReceiptLink") + 1 if "ReceiptLink" in headers else None

        matched = False
        for idx, row in enumerate(rows, start=2):
            phone = normalize_phone(row.get("PhoneNumber"))
            #  match if exactly equal OR endswith
            if phone == customer_id or customer_id.endswith(phone) or phone.endswith(customer_id):
                print(f"[Webhook] Payment matched for row {idx} (Phone: {phone})")
                matched = True

                try:
                    #  First update Txn & Receipt so we archive correct data
                    if txn_col:
                        sheets.sheet.update_cell(idx, txn_col, transaction_id or "")
                    if receipt_col:
                        sheets.sheet.update_cell(idx, receipt_col, receipt_url or "")

                    #  Archive the current state (keeps Penalty & Reminders as they are)
                    sheets.archive_and_reset_tenant(idx)

                    print(f"[Webhook] ✅ Row {idx} archived & reset for next month.")
                except Exception as e:
                    print(f"[Webhook] ❌ Error updating sheet for row {idx}: {e}")
                break

        if not matched:
            print(f"[Webhook] ⚠️ No matching phone found for {customer_id}")

    return {"status": "ok"}

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    d = "".join(c for c in str(phone) if c.isdigit())
    return d[-10:] if len(d) >= 10 else d


def get_manager_phone_from_db() -> str | None:
    """Fetch the landlord's manager number (fallback to landlord phone)."""
    with SessionLocal() as db:
        user = db.query(models.User).first()
        if not user:
            return None
        return normalize_phone(getattr(user, "manager_phone", None) or user.phone_number)


VERIFY_TOKEN = "myverifytoken123"  # same token you entered on Meta dashboard

@app.get("/whatsapp-webhook")
async def verify_webhook(request: Request):
    # Facebook/Meta calls GET for verification
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge)
    return Response(content="Verification failed", status_code=403)


@app.post("/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    body = await request.json()
    print("[WhatsApp Webhook]", body)

    entry = (body.get("entry") or [{}])[0]
    changes = (entry.get("changes") or [{}])[0]
    value = changes.get("value", {})
    messages = value.get("messages", [])
    if not messages:
        return {"status": "no_message"}

    msg = messages[0]

    if msg.get("type") == "button":
        payload = msg.get("button", {}).get("payload")
        tenant_phone = msg.get("from")
        print(f"[WhatsApp] Button clicked: {payload} from {tenant_phone}")

        # Match either text or payload
        if payload and payload.lower().strip() in ["pay in cash", "pay_cash"]:
            otp = cash_otp.generate_otp()
            cash_otp.set_otp(tenant_phone, otp, ttl=300)

            # 🔥 get manager number from DB or default
            manager_phone = get_manager_phone_from_db() or DEFAULT_MANAGER
            await whatsapp.send_otp(manager_phone, otp)
            print(f"[OTP] Sent to manager {manager_phone} for tenant {tenant_phone}")

    return {"status": "ok"}




MANAGER_PHONE = os.getenv("MANAGER_PHONE")  # Manager gets the OTP

@app.post("/cash-payment/request-otp")
async def request_cash_otp(
    tenant_phone: str,
    current_user: models.User = Depends(get_current_user)
):
    """
    Called when tenant clicks 'Pay in Cash' button.
    Generates an OTP and sends it to the manager via WhatsApp.
    """
    # 1. Generate OTP
    otp = cash_otp.generate_otp()
    cash_otp.set_otp(tenant_phone, otp, ttl=300)

    # 2. Fetch manager number from DB (must exist in models.User)
    manager_phone = getattr(current_user, "manager_phone", None)
    if not manager_phone:
        return {"status": "error", "message": "Manager phone not set for this landlord"}

    # 3. Send OTP to manager
    msg_text = f"OTP for tenant {tenant_phone}: {otp} (valid for 5 minutes)"
    status, resp = await whatsapp.send_message(manager_phone, msg_text)

    return {
        "status": "otp_sent",
        "manager_phone": manager_phone,
        "whatsapp_status": status,
        "whatsapp_response": resp,
    }

@app.post("/cash-payment/verify-otp")
async def verify_cash_otp(
    tenant_phone: str,
    otp: str,
    current_user: models.User = Depends(get_current_user)
):
    """
    Manager enters OTP received for tenant → marks tenant as Paid (Cash).
    """
    # 1. Validate OTP
    if not cash_otp.verify_otp(tenant_phone, otp):
        return {"status": "failed", "message": "Invalid or expired OTP"}

    # 2. Load tenant records
    rows = sheets.sheet.get_all_records()
    if not rows:
        return {"status": "failed", "message": "No tenants found in sheet"}

    # Normalize input phone
    tenant_digits = normalize_phone(tenant_phone)
    matched = False
    updated_row = None

    # 3. Match tenant and mark as Paid
    for idx, row in enumerate(rows, start=2):
        phone = normalize_phone(row.get("PhoneNumber"))
        if phone == tenant_digits or tenant_digits.endswith(phone) or phone.endswith(tenant_digits):
            print(f"[Cash Payment] ✅ OTP verified. Marking tenant {phone} (row {idx}) as Paid.")
            sheets.archive_and_reset_tenant(idx, payment_mode="Cash")
            matched = True
            updated_row = idx
            break

    if not matched:
        return {"status": "failed", "message": f"Tenant {tenant_phone} not found in sheet"}

    return {
        "status": "success",
        "message": f"Tenant {tenant_phone} marked as Paid (Cash)",
        "row": updated_row
    }


@app.get("/user/form-status")
async def user_form_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns whether the landlord has already configured settings.
    """
    has_config = (
        bool(current_user.google_sheet_url)
        and bool(current_user.daily_penalty)
        and bool(current_user.reminder_time_1)
    )

    return {"submitted": has_config}




@app.get("/user/config")
async def get_user_config(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Return saved landlord configuration for pre-filling the form.
    """
    return {
        "sheet_url": current_user.google_sheet_url or "",
        "penalty_amount": current_user.daily_penalty or "",
        "reminder_time_1": current_user.reminder_time_1 or "",
        "reminder_time_2": current_user.reminder_time_2 or "",
        "phone_number": current_user.phone_number or "",
        "manager_phone": current_user.manager_phone or "",
    }




@app.get("/get-config")
async def get_config(current_user: models.User = Depends(get_current_user), db: Session = Depends(db.SessionLocal)):
    """
    Fetches the landlord's configuration details for pre-filling the form.
    """
    user = db.query(models.User).filter(models.User.email == current_user.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    config = db.query(models.LandlordConfig).filter(models.LandlordConfig.user_id == user.id).first()
    if not config:
        return {
            "sheet_url": "",
            "penalty_amount": "",
            "reminder_time_1": "",
            "reminder_time_2": "",
            "phone_number": "",
        }

    return {
        "sheet_url": config.sheet_url,
        "penalty_amount": config.penalty_amount,
        "reminder_time_1": config.reminder_time_1,
        "reminder_time_2": config.reminder_time_2,
        "phone_number": config.phone_number,
    }
    
@app.get("/user/form-status")
async def get_form_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(db.SessionLocal)
):
    """
    Checks if the landlord has already completed configuration.
    """
    user = db.query(models.User).filter(models.User.email == current_user.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    config = db.query(models.LandlordConfig).filter(models.LandlordConfig.user_id == user.id).first()
    return {"submitted": bool(config)}
    
  
# @app.get("/dashboard-data")
# async def get_dashboard_data(
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(get_current_user)
# ):
#     """
#     Fetch data from Google Sheet and calculate Expected vs Collected rent
#     including Paid History.
#     """
#     try:
#         # ✅ Load the user's sheet
#         sh = sheets.client.open_by_url(current_user.google_sheet_url)
#         main_sheet = sh.sheet1
#         all_data = main_sheet.get_all_records()

#         total_expected = 0
#         total_collected = 0

#         # ✅ 1️⃣ Calculate from main "Payments" sheet
#         for row in all_data:
#             amount = float(row.get("Amount", 0))
#             penalty = float(row.get("Penalty", 0))
#             status = str(row.get("PaymentStatus", "")).strip().lower()

#             total_expected += amount + penalty
#             if status == "paid":
#                 total_collected += amount + penalty

#         # ✅ 2️⃣ Try to include data from "Paid History"
#         try:
#             paid_ws = sh.worksheet("Paid History")
#             paid_rows = paid_ws.get_all_records()
#             for row in paid_rows:
#                 amount = float(row.get("Amount", 0))
#                 penalty = float(row.get("Penalty", 0))
#                 total_collected += amount + penalty
#         except Exception as e:
#             print("[Sheets] ℹ️ No 'Paid History' sheet found, skipping.")

#         return {
#             "status": "ok",
#             "expected": total_expected,
#             "collected": total_collected,
#         }

#     except Exception as e:
#         print("⚠️ Dashboard Error:", str(e))
#         return {"status": "error", "message": str(e)}
  
  
  
  
  


@app.get("/dashboard-data")
async def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Month-wise Expected vs Collected rent (3 months before + current + next month)
    """
    try:
        sh = sheets.client.open_by_url(current_user.google_sheet_url)
        main_sheet = sh.sheet1
        all_rows = main_sheet.get_all_records()

        monthly_data = defaultdict(lambda: {"expected": 0, "collected": 0})

        # ✅ Process "Payments" sheet
        for row in all_rows:
            try:
                amount = float(row.get("Amount", 0))
                penalty = float(row.get("Penalty", 0))
                due_str = str(row.get("DueDate", "")).strip()
                status = str(row.get("PaymentStatus", "")).strip().lower()

                if not due_str:
                    continue

                due_date = datetime.strptime(due_str, "%Y-%m-%d")
                month_key = due_date.strftime("%b %Y")  # e.g., "Oct 2025"

                monthly_data[month_key]["expected"] += amount + penalty
                if status == "paid":
                    monthly_data[month_key]["collected"] += amount + penalty

            except Exception as e:
                print(f"[Dashboard] Skipped row: {e}")

        # ✅ Include Paid History
        try:
            paid_ws = sh.worksheet("Paid History")
            paid_rows = paid_ws.get_all_records()
            for row in paid_rows:
                try:
                    amount = float(row.get("Amount", 0))
                    penalty = float(row.get("Penalty", 0))
                    archived = row.get("ArchivedAt", "")
                    if archived:
                        month_key = datetime.strptime(archived.split()[0], "%Y-%m-%d").strftime("%b %Y")
                        monthly_data[month_key]["collected"] += amount + penalty
                except Exception:
                    continue
        except:
            pass

        # ✅ Limit to (3 previous + current + next month)
        now = datetime.now()
        months_to_show = [
            (now.replace(day=1) - timedelta(days=30 * i)).strftime("%b %Y")
            for i in range(3, 0, -1)
        ] + [now.strftime("%b %Y"), (now.replace(day=28) + timedelta(days=30)).strftime("%b %Y")]

        response = {
            "status": "ok",
            "months": months_to_show,
            "expected": [monthly_data[m]["expected"] for m in months_to_show],
            "collected": [monthly_data[m]["collected"] for m in months_to_show],
        }

        return response

    except Exception as e:
        print("⚠️ Dashboard Error:", str(e))
        return {"status": "error", "message": str(e)}  
