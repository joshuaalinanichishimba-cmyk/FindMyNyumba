from app.core.database import engine, Base
from app.models.user import User
from app.models.listing import Listing

print("Dropping and recreating all tables...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Success! Database is now in sync with your code.")
