import sys, os
sys.path.append(os.getcwd())
from app.core.database import SessionLocal
from app.models.user import User

def fix_role():
    db = SessionLocal()
    user = db.query(User).first()
    if user:
        user.role = "student_host"
        db.commit()
        print(f"✅ DB SUCCESS: Account '{user.full_name}' converted to 'student_host'!")
    else:
        print("❌ DB ERROR: No users found.")
    db.close()

if __name__ == "__main__":
    fix_role()