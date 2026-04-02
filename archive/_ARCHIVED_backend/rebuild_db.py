from app.db.session import engine, SessionLocal
from app.db.base_class import Base
from app.models.user import User
from app.models.property import Property
from app.models.review import Review
from passlib.context import CryptContext

print("1. Dropping old tables...")
Base.metadata.drop_all(bind=engine)

print("2. Creating new tables...")
Base.metadata.create_all(bind=engine)

print("3. Adding admin user...")
db = SessionLocal()
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
hashed_pw = pwd_context.hash("YourPassword123!")

admin_user = User(
    email="joshua@test.com",
    hashed_password=hashed_pw,
    full_name="Joshua",
    role="admin"
)

try:
    db.add(admin_user)
    db.commit()
    print("\n--- SUCCESS! Database rebuilt and Admin created. ---")
except Exception as e:
    print(f"\nError: {e}")
    db.rollback()
finally:
    db.close()
