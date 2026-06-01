#!/usr/bin/env python3
"""
backend/scripts/verify_users.py

Quick verification script to check if users have been restored.
Run from the backend directory with:
    python scripts/verify_users.py

Shows all users in the database.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import SessionLocal
from app.models.user import User


def verify_users():
    """Check how many users exist in the database."""
    
    db = SessionLocal()
    
    try:
        users = db.query(User).all()
        
        if not users:
            print("\n" + "="*70)
            print("❌ NO USERS FOUND IN DATABASE")
            print("="*70)
            print("\nTo restore users, run:")
            print("  cd backend")
            print("  python scripts/restore_users.py")
            print("="*70 + "\n")
            return False
        
        print("\n" + "="*70)
        print(f"✅ FOUND {len(users)} USER(S) IN DATABASE")
        print("="*70)
        
        for user in users:
            print(f"\n  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Name: {user.full_name}")
            print(f"  Role: {user.role}")
            print(f"  Active: {'Yes' if user.is_active else 'No'}")
            print(f"  Verified: {'Yes' if user.is_verified else 'No'}")
            print(f"  Created: {user.created_at}")
        
        print("\n" + "="*70 + "\n")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = verify_users()
    sys.exit(0 if success else 1)
