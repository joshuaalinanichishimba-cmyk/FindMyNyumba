import sys
import os

# This line tells Python to look inside the current directory for the 'app' module
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.user import User
from app.models.property import Property
from app.core.security import hash_password

def seed_data():
    db = SessionLocal()
    try:
        # 1. Create a Sample Landlord
        landlord = db.query(User).filter(User.email == "landlord@nyumba.com").first()
        if not landlord:
            landlord = User(
                email="landlord@nyumba.com",
                hashed_password=hash_password("Nyumba2026!"),
                full_name="Bwalya Mwansa",
                role="landlord"
            )
            db.add(landlord)
            db.commit()
            db.refresh(landlord)
            print("✅ Landlord created: Bwalya Mwansa")

        # 2. Sample Property Data
        sample_listings = [
            {"title": "Modern 2-Bedroom Apartment", "price": 4500.0, "location": "Rhodes Park, Lusaka"},
            {"title": "Student Studio Near CBU", "price": 1200.0, "location": "Riverside, Kitwe"},
            {"title": "Luxury 4-Bedroom Villa", "price": 12000.0, "location": "Leopards Hill, Lusaka"},
            {"title": "Cozy Flat Near UNZA", "price": 2500.0, "location": "Handsworth, Lusaka"},
            {"title": "Family Home with Garden", "price": 5500.0, "location": "Kansenshi, Ndola"}
        ]

        # 3. Add Listings
        for item in sample_listings:
            existing = db.query(Property).filter(Property.title == item["title"]).first()
            if not existing:
                new_prop = Property(
                    title=item["title"],
                    price=item["price"],
                    location=item["location"],
                    owner_id=landlord.id,
                    description="Beautiful property with 24/7 security and modern fittings."
                )
                db.add(new_prop)
        
        db.commit()
        print(f"✅ Successfully seeded property listings!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
