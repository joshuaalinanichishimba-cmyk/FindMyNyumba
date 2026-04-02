import sys, os
sys.path.append(os.getcwd())
from app.core.database import SessionLocal
from app.models.user import User

def fix_role():
    db = SessionLocal()
    # Find the first active user and force their role to student_host
    user = db.query(User).first()
    if user:
        user.role = "student_host"
        db.commit()
        print(f"✅ SUCCESS: User '{user.full_name}' is now a officially a 'student_host'!")
    else:
        print("❌ No users found in the database.")
    db.close()

if __name__ == "__main__":
    fix_role()