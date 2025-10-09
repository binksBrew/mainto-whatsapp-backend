# Example (in Python shell)
from app.db import SessionLocal
from app import models
from app.auth import get_password_hash

db = SessionLocal()
user = models.User(
    email="landlord@example.com",
    password_hash=get_password_hash("mypassword")
)
db.add(user)
db.commit()
db.close()
