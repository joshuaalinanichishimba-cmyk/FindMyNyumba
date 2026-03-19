import sys
import os
# Add the current directory to path so we can import app modules
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Property, User # Ensure these match your actual model names

def inject_data():
    db = SessionLocal()
    try:
        # 1. Get an owner ID (Finding the first admin or landlord in your DB)
        owner = db.query(User).filter(User.role.in_(['admin', 'landlord'])).first()
        if not owner:
            print("❌ Error: No Admin or Landlord found in database. Please register an account first!")
            return

        # 2. Define 5 Realistic Zambian Listings
        listings = [
            {
                "title": "UNZA Luxury Student Studio",
                "description": "Modern studio apartment, 5 mins walk from Great East Road gate. Includes WiFi.",
                "price": 1500.0,
                "location": "Great East Road, Lusaka",
                "status": "active"
            },
            {
                "title": "Evelyn Hone 2-Bedroom Flat",
                "description": "Spacious flat near campus. Fully tiled with 24/7 water supply.",
                "price": 3200.0,
                "location": "Church Road, Lusaka",
                "status": "pending"
            },
            {
                "title": "CBU Riverside Bedsitter",
                "description": "Affordable bedsitter for serious students. Secure fencing and quiet environment.",
                "price": 1200.0,
                "location": "Riverside, Kitwe",
                "status": "active"
            },
            {
                "title": "Mulungushi University Boarding",
                "description": "Clean rooms with shared kitchen and hot showers. Transport to campus available.",
                "price": 1000.0,
                "location": "Kabwe Central",
                "status": "active"
            },
            {
                "title": "Apex Medical Uni Hostel",
                "description": "Premium student housing with study lounge and laundry services.",
                "price": 2000.0,
                "location": "Chalala, Lusaka",
                "status": "active"
            }
        ]

        # 3. Inject them
        for item in listings:
            new_prop = Property(
                title=item['title'],
                description=item['description'],
                price=item['price'],
                location=item['location'],
                status=item['status'],
                owner_id=owner.id
            )
            db.add(new_prop)
        
        db.commit()
        print(f"✅ SUCCESS: 5 realistic Zambian properties injected under owner: {owner.email}")

    except Exception as e:
        db.rollback()
        print(f"❌ DATABASE ERROR: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    inject_data()
