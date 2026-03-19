import sys, os
sys.path.append(os.getcwd())
from app.core.database import SessionLocal
from app.models.listing import Listing

def seed():
    db = SessionLocal()
    houses = [
        {"title": "Luxury En-suite - Kabulonga", "price": 4500, "location": "Kabulonga, Lusaka", "image_url": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=500"},
        {"title": "Modern Studio - Riverside", "price": 2800, "location": "Riverside, Kitwe", "image_url": "https://images.unsplash.com/photo-1502672260266-1c1de24244e4?w=500"},
        {"title": "Cozy Bed-space - Chelston", "price": 1200, "location": "Chelston, Lusaka", "image_url": "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=500"}
    ]
    for h in houses:
        if not db.query(Listing).filter(Listing.title == h["title"]).first():
            db.add(Listing(**h))
    db.commit()
    print("🏠 SUCCESS: 3 beautiful properties injected into your database!")

if __name__ == "__main__": seed()