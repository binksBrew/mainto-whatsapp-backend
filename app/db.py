# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os


# Load database URL from .env or default to local SQLite
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
DATABASE_URL=os.getenv("DATABASE_URL")

print(f"[DB DEBUG] DATABASE_URL = {os.getenv('DATABASE_URL')}")

# For SQLite you need connect_args
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency to get DB session inside FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
