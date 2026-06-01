#!/usr/bin/env python3
"""
backend/scripts/init_and_restore.py

Initialization script that runs on app startup.
- Creates database tables if they don't exist
- Restores test users if database is empty
- Idempotent — safe to run on every deployment

This script is called from the start command in render.yaml or Procfile.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import SessionLocal, Base, engine
from app.core.security import get_password_hash
from app.models.user import User


def init_database():
    """Create all tables."""
    print("\n🔧 Initializing database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables ready")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False


def restore_test_users():
    """Restore test users if database is empty."""
    db = SessionLocal()
    
    try:
        # Check if users already exist
        user_count = db.query(User).count()
        
        if user_count > 0:
            print(f"⏭️  Database already has {user_count} user(s), skipping restoration")
            return True
        
        print("\n📝 Restoring test users...")
        
        test_users = [
            {
                "email": "student@findmynyumba.com",
                "full_name": "John Doe",
                "password": "SecurePassword123!",
                "role": "student",
                "phone_number": "+254712345678",
            },
            {
                "email": "landlord@findmynyumba.com",
                "full_name": "Jane Smith",
                "password": "SecurePassword456!",
                "role": "landlord",
                "phone_number": "+254787654321",
                "business_name": "Premium Housing Solutions",
                "business_location": "Nairobi, Kenya",
            },
            {
                "email": "admin@findmynyumba.com",
                "full_name": "Admin User",
                "password": "AdminSecure789!",
                "role": "admin",
                "phone_number": "+254700000000",
                "is_verified": True,
            },
        ]
        
        for user_data in test_users:
            password = user_data.pop("password")
            new_user = User(
                **user_data,
                hashed_password=get_password_hash(password),
                is_active=True,
                is_verified=user_data.get("is_verified", False),
            )
            db.add(new_user)
            print(f"  ✅ Created {user_data['email']} ({user_data['role']})")
        
        db.commit()
        print("\n✅ Test users restored successfully\n")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error restoring users: {e}\n")
        return False
    finally:
        db.close()


def main():
    """Run initialization and restoration."""
    print("\n" + "="*70)
    print("🚀 FindMyNyumba Database Initialization")
    print("="*70)
    
    if not init_database():
        sys.exit(1)
    
    if not restore_test_users():
        sys.exit(1)
    
    print("="*70)
    print("✅ Initialization complete. Starting app...")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
