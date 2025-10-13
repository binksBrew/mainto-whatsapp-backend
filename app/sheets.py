# import gspread
# from google.oauth2.service_account import Credentials
# from datetime import datetime, date, timedelta
# import os
# import json
# import sys

# SCOPES = [
#     "https://www.googleapis.com/auth/spreadsheets",
#     "https://www.googleapis.com/auth/drive"
# ]

# # 🔹 Required columns in Google Sheet
# REQUIRED_COLUMNS = [
#     "Name", "PhoneNumber", "Amount", "DueDate",
#     "PaymentStatus", "Penalty", "NoOfReminders",
#     "TransactionID", "ReceiptLink"
# ]


# # if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
# #     # 🔸 Running on AWS ECS (secret injected via environment variable)
# #     print("[Sheets] Using GOOGLE_SERVICE_ACCOUNT_JSON from environment")
# #     service_account_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
# #     creds_info = json.loads(service_account_json)
# #     creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
# # else:
# #     # 🔸 Running locally (for debugging/development)
# #     print("[Sheets] Using local service_account.json file")
# #     creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)

# # # Initialize Google Sheets client
# # client = gspread.authorize(creds)
# # sheet = None

# # # Helpers
# # def get_headers():
# #     return sheet.row_values(1)

# # ------------------ CREDENTIALS SETUP ------------------
# try:
#     creds = None

#     if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
#         # 🔸 Running on AWS ECS (secret injected via environment variable)
#         print("[Sheets] Using GOOGLE_SERVICE_ACCOUNT_JSON from environment", flush=True)
#         service_account_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

#         # Ensure it's valid JSON before loading
#         creds_info = json.loads(service_account_json)
#         creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

#     else:
#         # 🔸 Running locally (for debugging/development)
#         print("[Sheets] Using local service_account.json file", flush=True)
#         creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)

#     # Initialize Google Sheets client
#     client = gspread.authorize(creds)
#     sheet = None
#     print("[Sheets] ✅ Google Sheets connection initialized successfully", flush=True)

# except Exception as e:
#     print(f"[Sheets] ❌ Failed to initialize Google Sheets: {str(e)}", file=sys.stderr, flush=True)
#     raise  # Re-raise to stop container startup if credentials are broken


# # ------------------ HELPERS ------------------
# def get_headers():
#     """Return header row from the sheet"""
#     if not sheet:
#         raise ValueError("Sheet not initialized.")
#     return sheet.row_values(1)

# # Get rows that should get reminders today
# def get_due_rows(default_daily_penalty: float = 0):
#     today = date.today()
#     due_rows = []
#     rows = sheet.get_all_records()

#     if not rows:
#         return []

#     headers = list(rows[0].keys())
#     missing = [col for col in REQUIRED_COLUMNS if col not in headers]
#     if missing:
#         print(f"[Sheets] ⚠️ Missing columns: {missing}")

#     for idx, row in enumerate(rows, start=2):
#         status = str(row.get("PaymentStatus", "")).strip().lower()
#         if status in ["", "none"]:
#             status = "pending"
#         if status != "pending":
#             continue

#         due_date_str = str(row.get("DueDate", "")).strip()
#         if not due_date_str:
#             continue
#         try:
#             due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
#         except:
#             continue

#         try:
#             penalty_per_day = float(row.get("PenaltyPerDay") or default_daily_penalty or 0)
#         except:
#             penalty_per_day = default_daily_penalty

#         try:
#             current_penalty = float(row.get("Penalty") or 0)
#         except:
#             current_penalty = 0

#         delta_days = (today - due_date).days
#         days_before = (due_date - today).days

#         # 🔹 3/2/1 days before
#         if days_before in [3, 2, 1]:
#             due_rows.append({**row, "_row_number": idx, "penalty_to_apply": 0, "new_penalty": current_penalty})
#         # 🔹 On due date
#         if delta_days == 0:
#             due_rows.append({**row, "_row_number": idx, "penalty_to_apply": 0, "new_penalty": current_penalty})
#         # 🔹 After due date — add daily penalty
#         if delta_days > 0:
#             new_penalty = current_penalty + penalty_per_day
#             due_rows.append({**row, "_row_number": idx, "penalty_to_apply": penalty_per_day, "new_penalty": new_penalty})

#     return due_rows


# # Update penalty and reminders count
# def update_penalty_and_reminders(row_number: int, new_penalty: float):
#     try:
#         current_reminders = sheet.cell(row_number, 7).value
#         current_reminders = int(current_reminders or 0)
#     except:
#         current_reminders = 0

#     sheet.update_cell(row_number, 6, new_penalty)
#     sheet.update_cell(row_number, 7, current_reminders + 1)



# #  Mark row as Paid (used if you don't want to archive)
# def mark_as_paid(row_number: int):
#     sheet.update_cell(row_number, 5, "Paid")
#     sheet.update_cell(row_number, 6, 0)
#     sheet.update_cell(row_number, 7, 0)


# #  Archive paid tenant to Paid History & reset for next cycle
# def archive_and_reset_tenant(row_number: int, payment_mode: str = "Online"):
#     """
#     1️⃣ Copy current row to 'Paid History' (keeping Penalty & NoOfReminders).
#     2️⃣ Mark PaymentStatus = Paid in history.
#     3️⃣ Reset the row for next month (Pending, clear Txn/Receipt, set new DueDate).
#     """
#     row_values = sheet.row_values(row_number)
#     headers = sheet.row_values(1)

#     if not row_values:
#         print(f"[Sheets] ⚠️ Row {row_number} is empty — skipping.")
#         return

#     # --- Build a dict for safe editing ---
#     row_dict = {headers[i]: row_values[i] if i < len(row_values) else "" for i in range(len(headers))}

#     #  Force PaymentStatus = Paid
#     row_dict["PaymentStatus"] = "Paid"
#     #  Add PaymentMode
#     row_dict["PaymentMode"] = payment_mode
#     #  Add ArchivedAt timestamp
#     row_dict["ArchivedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#     # --- Build the ordered row for appending ---
#     final_headers = headers.copy()
#     # Make sure PaymentMode & ArchivedAt exist
#     if "PaymentMode" not in final_headers:
#         final_headers.append("PaymentMode")
#     if "ArchivedAt" not in final_headers:
#         final_headers.append("ArchivedAt")

#     row_to_archive = [row_dict.get(h, "") for h in final_headers]

#     # --- Get or create Paid History sheet ---
#     sh = sheet.spreadsheet
#     try:
#         paid_ws = sh.worksheet("Paid History")
#         existing_headers = paid_ws.row_values(1)
#         if existing_headers != final_headers:
#             paid_ws.update("A1", [final_headers])
#     except gspread.exceptions.WorksheetNotFound:
#         paid_ws = sh.add_worksheet(title="Paid History", rows="100", cols=str(len(final_headers)))
#         paid_ws.insert_row(final_headers, 1)

#     paid_ws.append_row(row_to_archive)
#     print(f"[Sheets] ✅ Archived row {row_number} → Paid History ({payment_mode})")

#     # --- Reset the live row for next cycle ---
#     try:
#         due_date = datetime.strptime(str(row_dict.get("DueDate", datetime.today().strftime("%Y-%m-%d"))), "%Y-%m-%d").date()
#     except:
#         due_date = date.today()

#     next_due = due_date + timedelta(days=30)
#     next_due_str = next_due.strftime("%Y-%m-%d")

#     sheet.update_cell(row_number, headers.index("PaymentStatus") + 1, "Pending")
#     sheet.update_cell(row_number, headers.index("Penalty") + 1, 0)
#     sheet.update_cell(row_number, headers.index("NoOfReminders") + 1, 0)
#     if "TransactionID" in headers:
#         sheet.update_cell(row_number, headers.index("TransactionID") + 1, "")
#     if "ReceiptLink" in headers:
#         sheet.update_cell(row_number, headers.index("ReceiptLink") + 1, "")
#     sheet.update_cell(row_number, headers.index("DueDate") + 1, next_due_str)

#     print(f"[Sheets] Row {row_number} reset for next month → DueDate={next_due_str}")


# # Change the active Google Sheet dynamically
# # def set_sheet_by_url(url: str):
# #     global sheet
# #     sh = client.open_by_url(url)
# #     sheet = sh.sheet1

# # def set_sheet_by_url(url: str):
# #     global sheet
# #     sh = client.open_by_url(url)
# #     sheet = sh.sheet1
# #     return sheet


# # def set_sheet_by_url(url: str):
# #     global sheet
# #     try:
# #         sh = client.open_by_url(url)
# #         sheet = sh.sheet1
# #         print(f"[Sheets] ✅ Loaded sheet: {sh.title}")
# #         return sheet
# #     except Exception as e:
# #         print(f"[Sheets] ❌ Failed to open sheet from URL: {url}")
# #         print(f"[Sheets] Error: {e}")
# #         sheet = None
# #         return None


# def set_sheet_by_url(url: str):
#     global sheet
#     try:
#         sh = client.open_by_url(url)
#         sheet = sh.sheet1
#         print(f"[Sheets] ✅ Active sheet set: {url}")
#     except Exception as e:
#         sheet = None
#         print(f"[Sheets] ❌ Failed to load sheet: {e}")







import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import os
import json
import sys
import base64

# ------------------ SCOPES ------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ------------------ REQUIRED COLUMNS ------------------
REQUIRED_COLUMNS = [
    "Name", "PhoneNumber", "Amount", "DueDate",
    "PaymentStatus", "Penalty", "NoOfReminders",
    "TransactionID", "ReceiptLink"
]

# try:
#     creds = None
#     raw_env_value = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")

#     if raw_env_value:
#         print("[Sheets] Using Google credentials from environment", flush=True)

#         # Step 1: Base64-decode if needed
#         if not raw_env_value.strip().startswith("{"):
#             try:
#                 decoded_bytes = base64.b64decode(raw_env_value)
#                 raw_json = decoded_bytes.decode("utf-8")
#                 print("[Sheets] ✅ Base64 decoded successfully", flush=True)
#             except Exception as e:
#                 raise ValueError(f"Failed to decode base64 secret: {e}")
#         else:
#             raw_json = raw_env_value

#         # ✅ Step 2: Immediately escape any real newlines to make valid JSON
#         raw_json = raw_json.replace("\r", "").replace("\n", "\\n")

#         # Step 3: Now parse the JSON
#         try:
#             creds_info = json.loads(raw_json)
#             print("[Sheets] ✅ JSON parsed successfully", flush=True)
#         except json.JSONDecodeError as e:
#             print(f"[Sheets] ❌ JSON parse failed: {e}", flush=True)
#             print("---- RAW SNIPPET ----")
#             print(raw_json[:300])
#             print("---------------------")
#             raise

#         # Step 4: Create credentials
#         creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

#     else:
#         print("[Sheets] Using local service_account.json file", flush=True)
#         creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)

#     client = gspread.authorize(creds)
#     sheet = None
#     print("[Sheets] ✅ Google Sheets connection initialized successfully", flush=True)

# except Exception as e:
#     print(f"[Sheets] ❌ Failed to initialize Google Sheets: {e}", file=sys.stderr, flush=True)
#     sheet = None
#     raise

try:
    creds = None
    raw_env_value = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")

    if raw_env_value:
        print("[Sheets] Using Google credentials from environment", flush=True)

        # Step 1: Base64-decode if needed
        if not raw_env_value.strip().startswith("{"):
            try:
                decoded_bytes = base64.b64decode(raw_env_value)
                raw_json = decoded_bytes.decode("utf-8")
                print("[Sheets] ✅ Base64 decoded successfully", flush=True)
            except Exception as e:
                raise ValueError(f"Failed to decode base64 secret: {e}")
        else:
            raw_json = raw_env_value

        # ✅ Step 2: Decode any escaped characters like \n into real newlines
        # AWS Secrets Manager injects escaped characters, so convert them back
        raw_json_fixed = raw_json.encode("utf-8").decode("unicode_escape")

        # Step 3: Parse the JSON
        try:
            creds_info = json.loads(raw_json_fixed)
            print("[Sheets] ✅ JSON parsed successfully", flush=True)
        except json.JSONDecodeError as e:
            print(f"[Sheets] ❌ JSON parse failed: {e}", flush=True)
            print("---- RAW SNIPPET ----")
            print(raw_json[:300])
            print("---------------------")
            raise

        # Step 4: Create credentials
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

    else:
        print("[Sheets] Using local service_account.json file", flush=True)
        creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)

    client = gspread.authorize(creds)
    sheet = None
    print("[Sheets] ✅ Google Sheets connection initialized successfully", flush=True)

except Exception as e:
    print(f"[Sheets] ❌ Failed to initialize Google Sheets: {e}", file=sys.stderr, flush=True)
    sheet = None
    raise


# ------------------ HELPERS ------------------
def get_headers():
    """Return header row from the sheet"""
    if not sheet:
        raise ValueError("Sheet not initialized.")
    return sheet.row_values(1)


def get_due_rows(default_daily_penalty: float = 0):
    """Return all rows due for reminders or penalties."""
    if not sheet:
        raise ValueError("Sheet not initialized.")

    today = date.today()
    due_rows = []
    rows = sheet.get_all_records()

    if not rows:
        return []

    headers = list(rows[0].keys())
    missing = [col for col in REQUIRED_COLUMNS if col not in headers]
    if missing:
        print(f"[Sheets] ⚠️ Missing columns: {missing}", flush=True)

    for idx, row in enumerate(rows, start=2):
        status = str(row.get("PaymentStatus", "")).strip().lower() or "pending"
        if status != "pending":
            continue

        due_date_str = str(row.get("DueDate", "")).strip()
        if not due_date_str:
            continue

        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        penalty_per_day = float(row.get("PenaltyPerDay") or default_daily_penalty or 0)
        current_penalty = float(row.get("Penalty") or 0)

        delta_days = (today - due_date).days
        days_before = (due_date - today).days

        # Pre-due reminders
        if days_before in [3, 2, 1]:
            due_rows.append({**row, "_row_number": idx, "penalty_to_apply": 0, "new_penalty": current_penalty})
        # On due date
        if delta_days == 0:
            due_rows.append({**row, "_row_number": idx, "penalty_to_apply": 0, "new_penalty": current_penalty})
        # After due date → add penalty
        if delta_days > 0:
            new_penalty = current_penalty + penalty_per_day
            due_rows.append({**row, "_row_number": idx, "penalty_to_apply": penalty_per_day, "new_penalty": new_penalty})

    return due_rows


def update_penalty_and_reminders(row_number: int, new_penalty: float):
    """Update penalty and increment reminders count."""
    if not sheet:
        raise ValueError("Sheet not initialized.")

    try:
        current_reminders = int(sheet.cell(row_number, 7).value or 0)
    except Exception:
        current_reminders = 0

    sheet.update_cell(row_number, 6, new_penalty)
    sheet.update_cell(row_number, 7, current_reminders + 1)
    print(f"[Sheets] 🔄 Updated row {row_number}: Penalty={new_penalty}, Reminders={current_reminders + 1}", flush=True)


def mark_as_paid(row_number: int):
    """Mark a row as paid."""
    if not sheet:
        raise ValueError("Sheet not initialized.")

    sheet.update_cell(row_number, 5, "Paid")
    sheet.update_cell(row_number, 6, 0)
    sheet.update_cell(row_number, 7, 0)
    print(f"[Sheets] 💰 Marked row {row_number} as Paid", flush=True)


def archive_and_reset_tenant(row_number: int, payment_mode: str = "Online"):
    """Archive a paid tenant to 'Paid History' and reset their live record."""
    if not sheet:
        raise ValueError("Sheet not initialized.")

    row_values = sheet.row_values(row_number)
    headers = sheet.row_values(1)
    if not row_values:
        print(f"[Sheets] ⚠️ Row {row_number} empty, skipping.", flush=True)
        return

    row_dict = {headers[i]: row_values[i] if i < len(row_values) else "" for i in range(len(headers))}
    row_dict["PaymentStatus"] = "Paid"
    row_dict["PaymentMode"] = payment_mode
    row_dict["ArchivedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    final_headers = headers.copy()
    if "PaymentMode" not in final_headers:
        final_headers.append("PaymentMode")
    if "ArchivedAt" not in final_headers:
        final_headers.append("ArchivedAt")

    row_to_archive = [row_dict.get(h, "") for h in final_headers]

    # Ensure Paid History exists
    sh = sheet.spreadsheet
    try:
        paid_ws = sh.worksheet("Paid History")
        existing_headers = paid_ws.row_values(1)
        if existing_headers != final_headers:
            paid_ws.update("A1", [final_headers])
    except gspread.exceptions.WorksheetNotFound:
        paid_ws = sh.add_worksheet(title="Paid History", rows="100", cols=str(len(final_headers)))
        paid_ws.insert_row(final_headers, 1)

    paid_ws.append_row(row_to_archive)
    print(f"[Sheets] ✅ Archived row {row_number} → Paid History ({payment_mode})", flush=True)

    # Reset row for next billing cycle
    try:
        due_date = datetime.strptime(str(row_dict.get("DueDate", date.today().strftime("%Y-%m-%d"))), "%Y-%m-%d").date()
    except Exception:
        due_date = date.today()

    next_due = due_date + timedelta(days=30)
    next_due_str = next_due.strftime("%Y-%m-%d")

    sheet.update_cell(row_number, headers.index("PaymentStatus") + 1, "Pending")
    sheet.update_cell(row_number, headers.index("Penalty") + 1, 0)
    sheet.update_cell(row_number, headers.index("NoOfReminders") + 1, 0)

    if "TransactionID" in headers:
        sheet.update_cell(row_number, headers.index("TransactionID") + 1, "")
    if "ReceiptLink" in headers:
        sheet.update_cell(row_number, headers.index("ReceiptLink") + 1, "")

    sheet.update_cell(row_number, headers.index("DueDate") + 1, next_due_str)
    print(f"[Sheets] 🔁 Row {row_number} reset for next month → DueDate={next_due_str}", flush=True)


def set_sheet_by_url(url: str):
    """Set the active Google Sheet by URL."""
    global sheet
    try:
        sh = client.open_by_url(url)
        sheet = sh.sheet1
        print(f"[Sheets] ✅ Active sheet set: {url}", flush=True)
    except Exception as e:
        sheet = None
        print(f"[Sheets] ❌ Failed to load sheet: {e}", file=sys.stderr, flush=True)
