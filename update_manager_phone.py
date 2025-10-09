# # import os
# # import sys
# # import sqlalchemy
# # from sqlalchemy.orm import sessionmaker
# # from app import models, database  # <-- adjust import path if needed

# # # ======================
# # # ✅ DB Setup
# # # ======================
# # # If you have DATABASE_URL in .env, we can reuse it:
# # DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")  # <-- change if needed

# # engine = sqlalchemy.create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
# # SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# # # ======================
# # # ✅ Update manager number
# # # ======================
# # def update_manager(manager_email: str, new_phone: str):
# #     db = SessionLocal()
# #     try:
# #         user = db.query(models.User).filter(models.User.email == manager_email).first()
# #         if not user:
# #             print(f"❌ No user found with email: {manager_email}")
# #             return
# #         user.phone_number = new_phone
# #         db.commit()
# #         print(f"✅ Manager phone updated to {new_phone} for {manager_email}")
# #     except Exception as e:
# #         print(f"❌ Error updating manager: {e}")
# #     finally:
# #         db.close()


# # if __name__ == "__main__":
# #     if len(sys.argv) < 3:
# #         print("Usage: python update_manager_number.py <manager_email> <new_phone_number>")
# #         print("Example: python update_manager_number.py landlord@example.com 9179722 94961")
# #         sys.exit(1)
# #     email = sys.argv[1]
# #     phone = sys.argv[2]
# #     update_manager(email, phone)






# import os
# import sys
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from app import models

# # =========================================================
# # 🔹 Get DATABASE_URL from .env or default to SQLite file
# # =========================================================
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# # For SQLite: need special connect_args
# if DATABASE_URL.startswith("sqlite"):
#     engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
# else:
#     engine = create_engine(DATABASE_URL)

# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# def update_manager(email: str, new_phone: str):
#     db = SessionLocal()
#     try:
#         user = db.query(models.User).filter(models.User.email == email).first()
#         if not user:
#             print(f"❌ No user found with email: {email}")
#             return
#         user.phone_number = new_phone
#         db.commit()
#         print(f"✅ Manager phone updated to {new_phone} for {email}")
#     except Exception as e:
#         print(f"❌ Error updating manager: {e}")
#     finally:
#         db.close()


# if __name__ == "__main__":
#     if len(sys.argv) < 3:
#         print("Usage: python update_manager_number.py <manager_email> <new_phone_number>")
#         print("Example: python update_manager_number.py landlord@example.com +919422494809")
#         sys.exit(1)

#     email = sys.argv[1]
#     phone = sys.argv[2]
#     update_manager(email, phone)





# update_manager_phone.py
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models  # you already have your User model here
from sqlalchemy.engine.url import make_url

# --- CHANGE THIS if your DB URL is not in env but in alembic.ini ---
DATABASE_URL = "sqlite:///./app.db"   # fallback

try:
    # Try to import from your project if DATABASE_URL is already defined
    from app.config import DATABASE_URL as PROJECT_DB_URL
    DATABASE_URL = PROJECT_DB_URL
except Exception:
    pass

# Create engine + session
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def update_manager(email: str, new_phone: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"❌ User with email {email} not found")
            return
        old_phone = user.manager_phone
        user.manager_phone = new_phone
        db.commit()
        print(f"✅ Updated manager_phone for {email}: {old_phone} → {new_phone}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python update_manager_phone.py <email> <new_phone>")
        sys.exit(1)

    update_manager(sys.argv[1], sys.argv[2])
