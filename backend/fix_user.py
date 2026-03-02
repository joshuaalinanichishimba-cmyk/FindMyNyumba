from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password
import os

db = SessionLocal()
email = "john@example.com"
password = "yourpassword"

hashed = hash_password(password)
user = db.query(User).filter(User.email == email).first()

if user:
    user.hashed_password = hashed
    print("SUCCESS: User updated in test.db")
else:
    new_user = User(email=email, hashed_password=hashed, full_name="John Doe")
    db.add(new_user)
    print("SUCCESS: User created in test.db")

db.commit()
db.close()
