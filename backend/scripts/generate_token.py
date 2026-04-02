import sys, os
sys.path.append(os.getcwd())
from app.core.database import SessionLocal
from app.models.user import User

try:
    # Try common locations for the token generator
    from app.core.security import create_access_token
except ImportError:
    try:
        from app.auth import create_access_token
    except ImportError:
        print("❌ Could not locate create_access_token. Please log in normally via login.html.")
        sys.exit()

def generate_magic_token():
    db = SessionLocal()
    user = db.query(User).first()
    
    if not user:
        print("❌ No users found in the database. Please register an account first.")
        return

    # Force user to be a student host for testing
    user.role = "student_host"
    db.commit()
    
    # Generate a valid token
    token = create_access_token(data={"sub": user.email})
    
    print("\n" + "="*70)
    print("✅ SUCCESS! COPY THE LINE BELOW AND PASTE IT IN YOUR BROWSER CONSOLE (F12):")
    print("="*70 + "\n")
    print(f"localStorage.setItem('token', '{token}'); localStorage.setItem('role', 'student_host'); location.reload();")
    print("\n" + "="*70)
    
    db.close()

if __name__ == "__main__":
    generate_magic_token()