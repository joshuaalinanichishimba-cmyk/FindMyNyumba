from app.core.database import SessionLocal
from app.models.listing import Listing
from datetime import datetime, timedelta, timezone
db = SessionLocal()
l = db.query(Listing).filter(Listing.id==3).first()
l.is_boosted = True
l.boost_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
l.boost_tier = "fast_tenant"
db.commit()
print(f"Boosted listing 3 until {l.boost_expires_at}")
db.close()
