#!/usr/bin/env python3
"""
backend/scripts/restore_users.py

Database restoration script: Creates test users with proper password hashing.
This is the best approach for recovering from deleted users because it:
  1. Properly hashes passwords using the same security as registration
  2. Creates users with all required fields (role, is_active, is_verified)
  3. Can be run immediately without manual SQL
  4. Idempotent — won't create duplicates if re-run

Usage:
  cd backend
  python scripts/restore_users.py
"""

import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import SessionLocal, Base, engine
from app.core.security import get_password_hash
from app.models.user import User


def restore_users():
    """Restore default test users to the database."""
    
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Define test users to restore
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
        
        restored_count = 0
        skipped_count = 0
        
        for user_data in test_users:
            # Check if user already exists
            existing_user = db.query(User).filter(
                User.email == user_data["email"]
            ).first()
            
            if existing_user:
                print(f"⏭️  SKIPPED: {user_data['email']} (already exists)")
                skipped_count += 1
                continue
            
            # Create new user with hashed password
            password = user_data.pop("password")
            new_user = User(
                **user_data,
                hashed_password=get_password_hash(password),
                is_active=True,
                is_verified=user_data.get("is_verified", False),
            )
            
            db.add(new_user)
            print(f"✅ RESTORED: {user_data['email']} (role: {user_data['role']})")
            restored_count += 1
        
        # Commit all changes
        db.commit()
        
        # Print summary
        print("\n" + "="*70)
        print(f"✅ RESTORATION COMPLETE")
        print("="*70)
        print(f"  Restored: {restored_count} users")
        print(f"  Skipped:  {skipped_count} users (already exist)")
        print("\n📝 TEST CREDENTIALS:")
        print("="*70)
        print("  Student:")
        print("    Email:    student@findmynyumba.com")
        print("    Password: SecurePassword123!")
        print("\n  Landlord:")
        print("    Email:    landlord@findmynyumba.com")
        print("    Password: SecurePassword456!")
        print("\n  Admin:")
        print("    Email:    admin@findmynyumba.com")
        print("    Password: AdminSecure789!")
        print("="*70 + "\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    restore_users()
