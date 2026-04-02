from app.core.database import SessionLocal
from app.models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin():
    db = SessionLocal()
    try:
        # Check if admin already exists
        existing_user = db.query(User).filter(User.email == "admin@findmynyumba.zm").first()
        if existing_user:
            print("👤 Admin already exists!")
            return

        new_admin = User(
            email="admin@findmynyumba.zm",
            hashed_password=pwd_context.hash("Zambia2026!"),
            full_name="Joshua Admin",
            role="admin",
            is_active=True
        )
        db.add(new_admin)
        db.commit()
        print("✅ Admin 'Joshua' successfully registered in FindMyNyumba!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
